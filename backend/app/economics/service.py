"""Economics records: owner-scoped CRUD on crop-cycle expenses and harvest/sales, plus the
per-cycle summary. Another user's ids answer 404; every write is audited in the same
transaction (CLAUDE.md hard rule 9)."""

import uuid
from dataclasses import asdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.errors import AppError
from app.economics import calc
from app.economics.models import Expense, HarvestSale
from app.economics.schemas import (
    CycleEconomicsOut,
    CycleRef,
    ExpenseIn,
    ExpenseOut,
    ExpenseUpdate,
    HarvestIn,
    HarvestOut,
    HarvestUpdate,
)
from app.farms import repository as farm_repo
from app.farms.models import CropCycle, Farm, Field
from app.identity.models import User

DEFINITIONS = [
    "Total cost = sum of recorded expenses (PKR).",
    "Revenue = sum of quantity x price for sold harvest lots (PKR); unsold lots add nothing.",
    "Profit = revenue - total cost (negative = loss).",
    "Cost per hectare / acre = total cost / field area (1 acre = 0.40468564224 ha).",
    "Break-even price = total cost / harvested kg (PKR per kg).",
    "Break-even yield = total cost / average sold price (kg).",
]
LIMITATIONS = [
    "Calculated only from the records you entered; nothing is estimated or filled in.",
    "Own labour, land value, interest and depreciation are included only if you record them.",
    "Quantities are kilograms only; maund is not offered until an official definition is recorded.",
]


def _owned_cycle_row(db: Session, user: User, cycle_id: uuid.UUID) -> Any:
    row = farm_repo.get_cycle_row(db, user.id, cycle_id)
    if row is None:
        raise AppError("not_found", "Crop cycle not found.", 404)
    return row


def _owned[M: (Expense, HarvestSale)](
    db: Session, user: User, model: type[M], record_id: uuid.UUID
) -> M:
    rec = db.scalar(
        select(model)
        .join(CropCycle, CropCycle.id == model.crop_cycle_id)
        .join(Field, Field.id == CropCycle.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .where(model.id == record_id, Farm.owner_id == user.id)
    )
    if rec is None:
        raise AppError("not_found", "Record not found.", 404)
    return rec


def harvest_out(h: HarvestSale) -> HarvestOut:
    out = HarvestOut.model_validate(h)
    if h.price_pkr_per_kg is not None:
        out.revenue_pkr = calc.money(h.quantity_kg * h.price_pkr_per_kg)
    return out


def _audit(
    db: Session,
    user: User,
    action: str,
    rec: Expense | HarvestSale,
    rid: str | None,
    fields: list[str] | None = None,
) -> None:
    entity = "expense" if isinstance(rec, Expense) else "harvest_sale"
    meta: dict[str, Any] = {"crop_cycle_id": str(rec.crop_cycle_id)}
    if fields is not None:
        meta["fields"] = sorted(fields)
    audit.record(
        db,
        action=f"{entity}.{action}",
        entity=entity,
        entity_id=rec.id,
        actor_id=user.id,
        meta=meta,
        request_id=rid,
    )


def create_expense(db: Session, user: User, data: ExpenseIn, rid: str | None) -> ExpenseOut:
    _owned_cycle_row(db, user, data.crop_cycle_id)
    rec = Expense(created_by=user.id, **data.model_dump())
    db.add(rec)
    db.flush()
    _audit(db, user, "created", rec, rid)
    db.commit()
    return ExpenseOut.model_validate(rec)


def create_harvest(db: Session, user: User, data: HarvestIn, rid: str | None) -> HarvestOut:
    _owned_cycle_row(db, user, data.crop_cycle_id)
    rec = HarvestSale(created_by=user.id, **data.model_dump())
    db.add(rec)
    db.flush()
    _audit(db, user, "created", rec, rid)
    db.commit()
    return harvest_out(rec)


def update[M: (Expense, HarvestSale)](
    db: Session,
    user: User,
    model: type[M],
    record_id: uuid.UUID,
    data: ExpenseUpdate | HarvestUpdate,
    rid: str | None,
) -> M:
    rec = _owned(db, user, model, record_id)
    changes = data.model_dump(exclude_unset=True)
    for required in ("category", "amount_pkr", "incurred_on", "recorded_on", "quantity_kg"):
        if required in changes and changes[required] is None:
            raise AppError("validation_error", f"{required} cannot be empty.", 422, required)
    for k, v in changes.items():
        setattr(rec, k, v)
    _audit(db, user, "updated", rec, rid, list(changes))
    db.commit()
    return rec


def delete[M: (Expense, HarvestSale)](
    db: Session, user: User, model: type[M], record_id: uuid.UUID, rid: str | None
) -> None:
    rec = _owned(db, user, model, record_id)
    _audit(db, user, "deleted", rec, rid)
    db.delete(rec)
    db.commit()


def cycle_economics(db: Session, user: User, cycle_id: uuid.UUID) -> CycleEconomicsOut:
    cycle, field, farm, crop = _owned_cycle_row(db, user, cycle_id)
    expenses = list(
        db.scalars(
            select(Expense)
            .where(Expense.crop_cycle_id == cycle.id)
            .order_by(Expense.incurred_on.desc(), Expense.created_at.desc())
        )
    )
    harvests = list(
        db.scalars(
            select(HarvestSale)
            .where(HarvestSale.crop_cycle_id == cycle.id)
            .order_by(HarvestSale.recorded_on.desc(), HarvestSale.created_at.desc())
        )
    )
    s = calc.summarise(
        [(e.category.value, e.amount_pkr) for e in expenses],
        [calc.Lot(h.quantity_kg, h.price_pkr_per_kg) for h in harvests],
        field.area_ha,
    )
    return CycleEconomicsOut(
        cycle=CycleRef(
            id=cycle.id,
            crop_name=crop.name_en,
            field_name=field.name,
            farm_name=farm.name,
            status=cycle.status.value,
            area_ha=field.area_ha,
        ),  # fmt: skip
        expenses=[ExpenseOut.model_validate(e) for e in expenses],
        harvests=[harvest_out(h) for h in harvests],
        summary=asdict(s),  # type: ignore[arg-type]
        definitions=DEFINITIONS,
        limitations=LIMITATIONS,
    )


def cycle_has_records(db: Session, cycle_id: uuid.UUID) -> bool:
    return any(
        db.scalar(select(m.id).where(m.crop_cycle_id == cycle_id).limit(1)) is not None
        for m in (Expense, HarvestSale)
    )
