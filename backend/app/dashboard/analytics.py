"""Owner-scoped analytics for the dashboard: grouped SQL over the user's own records only.
No estimates: every number is a count or a sum of stored rows (money in PKR, area in ha).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crop_health.models import CaseStatus, CropHealthCase
from app.economics.calc import money
from app.economics.models import Expense, HarvestSale
from app.farms.models import CropCycle, CropDefinition, CycleStatus, Farm, Field

MONTHS = 6


def _owned_cycles(owner_id: uuid.UUID) -> Any:
    return (
        select(CropCycle.id)
        .join(Field, Field.id == CropCycle.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .where(Farm.owner_id == owner_id)
    )


def _area_by_crop(db: Session, owner_id: uuid.UUID) -> list[dict[str, Any]]:
    """Growing (active) cycles per crop; area = cycle area if recorded, else its field's area."""
    area = func.coalesce(CropCycle.area_ha, Field.area_ha)
    rows = db.execute(
        select(CropDefinition.name_en, func.count(CropCycle.id), func.sum(area))
        .join(CropCycle, CropCycle.crop_id == CropDefinition.id)
        .join(Field, Field.id == CropCycle.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .where(Farm.owner_id == owner_id, CropCycle.status == CycleStatus.ACTIVE)
        .group_by(CropDefinition.name_en)
        .order_by(func.sum(area).desc())
    ).all()
    return [{"crop": c, "cycles": n, "area_ha": float(a or 0)} for c, n, a in rows]


def _cases(db: Session, owner_id: uuid.UUID, now: datetime) -> dict[str, Any]:
    by_status = dict(
        db.execute(
            select(CropHealthCase.status, func.count())
            .where(CropHealthCase.owner_id == owner_id)
            .group_by(CropHealthCase.status)
        ).all()
    )
    month = func.date_trunc("month", CropHealthCase.created_at)
    monthly = dict(
        db.execute(
            select(month, func.count()).where(CropHealthCase.owner_id == owner_id).group_by(month)
        ).all()
    )
    months = []
    y, m = now.year, now.month
    for _ in range(MONTHS):
        months.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    counts = {(k.year, k.month): v for k, v in monthly.items()}
    return {
        "by_status": {s.value: by_status.get(s, 0) for s in CaseStatus},
        "by_month": [
            {"month": f"{yy:04d}-{mm:02d}", "cases": counts.get((yy, mm), 0)}
            for yy, mm in reversed(months)
        ],
    }


def _economics(db: Session, owner_id: uuid.UUID) -> dict[str, Any]:
    owned = _owned_cycles(owner_id)
    by_cat = {
        c.value: money(v)
        for c, v in db.execute(
            select(Expense.category, func.sum(Expense.amount_pkr))
            .where(Expense.crop_cycle_id.in_(owned))
            .group_by(Expense.category)
        ).all()
    }
    cost_by_cycle = dict(
        db.execute(
            select(Expense.crop_cycle_id, func.sum(Expense.amount_pkr))
            .where(Expense.crop_cycle_id.in_(owned))
            .group_by(Expense.crop_cycle_id)
        ).all()
    )
    rev = HarvestSale.quantity_kg * HarvestSale.price_pkr_per_kg
    rev_by_cycle = dict(
        db.execute(
            select(HarvestSale.crop_cycle_id, func.coalesce(func.sum(rev), 0))
            .where(HarvestSale.crop_cycle_id.in_(owned))
            .group_by(HarvestSale.crop_cycle_id)
        ).all()
    )
    ids = set(cost_by_cycle) | set(rev_by_cycle)
    names = {
        cid: (crop, fld)
        for cid, crop, fld in db.execute(
            select(CropCycle.id, CropDefinition.name_en, Field.name)
            .join(CropDefinition, CropDefinition.id == CropCycle.crop_id)
            .join(Field, Field.id == CropCycle.field_id)
            .where(CropCycle.id.in_(ids))
        ).all()
    }
    zero = Decimal(0)
    cycles = []
    for cid in ids:
        cost, revenue = cost_by_cycle.get(cid, zero), rev_by_cycle.get(cid, zero)
        crop, fld = names[cid]
        cycles.append(
            {
                "crop_cycle_id": cid,
                "crop": crop,
                "field": fld,
                "cost_pkr": money(cost),
                "revenue_pkr": money(revenue),
                "profit_pkr": money(revenue - cost),
            }
        )
    cycles.sort(key=lambda c: c["profit_pkr"])
    total_cost = sum(cost_by_cycle.values(), zero)
    total_rev = sum(rev_by_cycle.values(), zero)
    return {
        "currency": "PKR",
        "total_cost_pkr": money(total_cost),
        "total_revenue_pkr": money(total_rev),
        "profit_pkr": money(total_rev - total_cost),
        "cost_by_category_pkr": dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
        "cycles": cycles,
    }


def summary(db: Session, owner_id: uuid.UUID, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    cases = _cases(db, owner_id, now)
    return {
        "generated_at": now,
        "area_by_crop": _area_by_crop(db, owner_id),
        "cases": cases,
        "pending_expert_reviews": cases["by_status"][CaseStatus.EXPERT_REVIEW.value],
        "economics": _economics(db, owner_id),
    }
