"""Farm domain service: ownership, business rules, audit, output mapping.

Public functions are what other modules (and future agent tools) call. In particular
`get_owned_cycle_context` is the single entry point for "is this crop cycle the
user's, and what field/farm does it belong to?" (Crop Doctor, irrigation, ...).
"""

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.errors import AppError
from app.core.pagination import Page, to_page
from app.farms import repository as repo
from app.farms.models import CropCycle, CycleStatus, Farm, Field
from app.farms.schemas import (
    AreaOut,
    CropCycleCreate,
    CropCycleOut,
    CropCycleUpdate,
    CropOut,
    FarmCreate,
    FarmOut,
    FarmUpdate,
    FieldCreate,
    FieldOut,
    FieldUpdate,
)
from app.identity.models import User
from app.units.area import to_hectares

MAX_FIELD_HA = Decimal(100_000)
EARLIEST_DATE = date(2000, 1, 1)
COORD_STEP = Decimal("0.01")


def _not_found(entity: str) -> AppError:
    return AppError("not_found", f"{entity} not found.", 404)


def _audit(db: Session, user: User, action: str, entity: str, eid: uuid.UUID, rid: str | None,
           fields: list[str] | None = None) -> None:  # fmt: skip
    meta = {"fields": sorted(fields)} if fields else None
    audit.record(db, action=action, entity=entity, entity_id=eid, actor_id=user.id,
                 meta=meta, request_id=rid)  # fmt: skip


def _coarse(value: Decimal | None) -> Decimal | None:
    return None if value is None else value.quantize(COORD_STEP, rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------------ farms


def _farm_out(row: Any) -> FarmOut:
    farm, field_count, total_area = row
    out = FarmOut.model_validate(farm)
    return out.model_copy(update={"field_count": field_count, "total_area_ha": float(total_area)})


def list_farms(db: Session, user: User, q: str | None, limit: int, cursor: str | None
               ) -> Page[FarmOut]:  # fmt: skip
    return to_page([_farm_out(r) for r in repo.list_farms(db, user.id, q, limit, cursor)], limit)


def get_farm(db: Session, user: User, farm_id: uuid.UUID) -> FarmOut:
    row = repo.get_farm_row(db, user.id, farm_id)
    if row is None:
        raise _not_found("Farm")
    return _farm_out(row)


def create_farm(db: Session, user: User, data: FarmCreate, rid: str | None) -> FarmOut:
    if repo.farm_name_taken(db, user.id, data.name):
        raise AppError("name_taken", "You already have a farm with this name.", 409, "name")
    values = data.model_dump()
    values["latitude"], values["longitude"] = _coarse(data.latitude), _coarse(data.longitude)
    farm = Farm(owner_id=user.id, **values)
    db.add(farm)
    db.flush()
    _audit(db, user, "farm.created", "farm", farm.id, rid)
    db.commit()
    return get_farm(db, user, farm.id)


def update_farm(db: Session, user: User, farm_id: uuid.UUID, data: FarmUpdate, rid: str | None
                ) -> FarmOut:  # fmt: skip
    farm = repo.get_owned_farm(db, user.id, farm_id)
    if farm is None:
        raise _not_found("Farm")
    changes = data.model_dump(exclude_unset=True)
    if changes.get("name") is None:
        changes.pop("name", None)  # name cannot be cleared
    elif repo.farm_name_taken(db, user.id, changes["name"], exclude=farm.id):
        raise AppError("name_taken", "You already have a farm with this name.", 409, "name")
    for key in ("latitude", "longitude"):
        if key in changes:
            changes[key] = _coarse(changes[key])
    lat = changes.get("latitude", farm.latitude)
    lon = changes.get("longitude", farm.longitude)
    if (lat is None) != (lon is None):
        raise AppError("validation_error", "Latitude and longitude must be set together.",
                       422, "latitude")  # fmt: skip
    for key, value in changes.items():
        setattr(farm, key, value)
    if changes:
        _audit(db, user, "farm.updated", "farm", farm.id, rid, list(changes))
    db.commit()
    return get_farm(db, user, farm.id)


def delete_farm(db: Session, user: User, farm_id: uuid.UUID, rid: str | None) -> None:
    farm = repo.get_owned_farm(db, user.id, farm_id)
    if farm is None:
        raise _not_found("Farm")
    if repo.farm_has_fields(db, farm.id):
        raise AppError("farm_not_empty", "Remove this farm's fields before deleting it.", 409)
    _audit(db, user, "farm.deleted", "farm", farm.id, rid)
    db.delete(farm)
    db.commit()


# ----------------------------------------------------------------------- fields


def _field_out(row: Any) -> FieldOut:
    field, farm_name, active = row
    return FieldOut(
        id=field.id, farm_id=field.farm_id, farm_name=farm_name, name=field.name,
        area=AreaOut(hectares=float(field.area_ha), value=float(field.area_input_value),
                     unit=field.area_input_unit, data_origin=field.area_origin),
        notes=field.notes, active_cycle_count=active,
        created_at=field.created_at, updated_at=field.updated_at,
    )  # fmt: skip


def _hectares(value: Decimal, unit: Any) -> Decimal:
    ha = to_hectares(value, unit).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    if ha <= 0 or ha > MAX_FIELD_HA:
        raise AppError("validation_error", "Field area must be between 0.0001 and 100,000 ha.",
                       422, "area")  # fmt: skip
    return ha


def list_fields(db: Session, user: User, farm_id: uuid.UUID | None, q: str | None, limit: int,
                cursor: str | None) -> Page[FieldOut]:  # fmt: skip
    rows = repo.list_fields(db, user.id, farm_id, q, limit, cursor)
    return to_page([_field_out(r) for r in rows], limit)


def get_field(db: Session, user: User, field_id: uuid.UUID) -> FieldOut:
    row = repo.get_field_row(db, user.id, field_id)
    if row is None:
        raise _not_found("Field")
    return _field_out(row)


def create_field(db: Session, user: User, data: FieldCreate, rid: str | None) -> FieldOut:
    if repo.get_owned_farm(db, user.id, data.farm_id) is None:
        raise AppError("not_found", "Farm not found.", 404, "farm_id")
    if repo.field_name_taken(db, data.farm_id, data.name):
        raise AppError("name_taken", "This farm already has a field with this name.", 409, "name")
    field = Field(
        farm_id=data.farm_id, name=data.name, notes=data.notes,
        area_ha=_hectares(data.area.value, data.area.unit), area_input_value=data.area.value,
        area_input_unit=data.area.unit, area_origin=data.area_origin,
    )  # fmt: skip
    db.add(field)
    db.flush()
    _audit(db, user, "field.created", "field", field.id, rid)
    db.commit()
    return get_field(db, user, field.id)


def update_field(db: Session, user: User, field_id: uuid.UUID, data: FieldUpdate,
                 rid: str | None) -> FieldOut:  # fmt: skip
    row = repo.get_field_row(db, user.id, field_id)
    if row is None:
        raise _not_found("Field")
    field: Field = row[0]
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes and repo.field_name_taken(db, field.farm_id, changes["name"], field.id):
        raise AppError("name_taken", "This farm already has a field with this name.", 409, "name")
    if data.area is not None:
        field.area_ha = _hectares(data.area.value, data.area.unit)
        field.area_input_value, field.area_input_unit = data.area.value, data.area.unit
    for key in ("name", "notes", "area_origin"):
        if key in changes:
            setattr(field, key, changes[key])
    if changes:
        _audit(db, user, "field.updated", "field", field.id, rid, list(changes))
    db.commit()
    return get_field(db, user, field.id)


def delete_field(db: Session, user: User, field_id: uuid.UUID, rid: str | None) -> None:
    row = repo.get_field_row(db, user.id, field_id)
    if row is None:
        raise _not_found("Field")
    if repo.field_has_cycles(db, field_id):
        raise AppError("field_not_empty", "This field has crop cycles and cannot be deleted.", 409)
    _audit(db, user, "field.deleted", "field", field_id, rid)
    db.delete(row[0])
    db.commit()


# ------------------------------------------------------------------ crop cycles


@dataclass(frozen=True)
class CycleState:
    status: CycleStatus
    sowing_date: date | None
    expected_harvest_date: date | None
    harvest_date: date | None
    area_ha: Decimal | None


def validate_cycle(s: CycleState, field_area_ha: Decimal, today: date) -> None:
    """Business rules for a crop cycle (pure; raises 422 AppError naming the field)."""

    def bad(message: str, field: str) -> AppError:
        return AppError("validation_error", message, 422, field)

    for name in ("sowing_date", "expected_harvest_date", "harvest_date"):
        value = getattr(s, name)
        if value is not None and value < EARLIEST_DATE:
            raise bad("Dates before 2000 are not accepted.", name)
    if s.sowing_date and s.sowing_date > today + timedelta(days=366):
        raise bad("Sowing date is more than a year ahead.", "sowing_date")
    if s.status in (CycleStatus.ACTIVE, CycleStatus.HARVESTED):
        if s.sowing_date is None:
            raise bad("A sowing date is required for this status.", "sowing_date")
        if s.sowing_date > today:
            raise bad("Sowing date cannot be in the future for this status.", "sowing_date")
    if s.status == CycleStatus.HARVESTED and s.harvest_date is None:
        raise bad("A harvest date is required for a harvested cycle.", "harvest_date")
    if s.harvest_date is not None:
        if s.harvest_date > today:
            raise bad("Harvest date cannot be in the future.", "harvest_date")
        if s.sowing_date and s.harvest_date < s.sowing_date:
            raise bad("Harvest date must be on or after the sowing date.", "harvest_date")
    if s.expected_harvest_date and s.sowing_date and s.expected_harvest_date < s.sowing_date:
        raise bad("Expected harvest must be on or after sowing.", "expected_harvest_date")
    if s.area_ha is not None and s.area_ha > field_area_ha:
        raise bad("Planted area cannot exceed the field area.", "area_ha")


def _cycle_out(row: Any) -> CropCycleOut:
    cycle, field, farm, crop = row
    return CropCycleOut(
        id=cycle.id, field_id=field.id, field_name=field.name, farm_id=farm.id,
        farm_name=farm.name, crop=CropOut.model_validate(crop), variety=cycle.variety,
        season=cycle.season, status=cycle.status, sowing_date=cycle.sowing_date,
        expected_harvest_date=cycle.expected_harvest_date, harvest_date=cycle.harvest_date,
        area_ha=float(cycle.area_ha) if cycle.area_ha is not None else None, notes=cycle.notes,
        created_at=cycle.created_at, updated_at=cycle.updated_at,
    )  # fmt: skip


def list_cycles(db: Session, user: User, limit: int, cursor: str | None,
                **filters: Any) -> Page[CropCycleOut]:  # fmt: skip
    rows = repo.list_cycles(db, user.id, limit=limit, cursor=cursor, **filters)
    return to_page([_cycle_out(r) for r in rows], limit)


def get_cycle(db: Session, user: User, cycle_id: uuid.UUID) -> CropCycleOut:
    row = repo.get_cycle_row(db, user.id, cycle_id)
    if row is None:
        raise _not_found("Crop cycle")
    return _cycle_out(row)


def get_owned_cycle_context(db: Session, user: User, cycle_id: uuid.UUID
                            ) -> tuple[CropCycle, Field, Farm]:  # fmt: skip
    """For other modules: the user's cycle with its field and farm, else 404."""
    row = repo.get_cycle_row(db, user.id, cycle_id)
    if row is None:
        raise _not_found("Crop cycle")
    return row[0], row[1], row[2]


def create_cycle(db: Session, user: User, data: CropCycleCreate, rid: str | None,
                 today: date) -> CropCycleOut:  # fmt: skip
    field_row = repo.get_field_row(db, user.id, data.field_id)
    if field_row is None:
        raise AppError("not_found", "Field not found.", 404, "field_id")
    if repo.get_active_crop(db, data.crop_id) is None:
        raise AppError("not_found", "Crop not found.", 404, "crop_id")
    values = data.model_dump()
    validate_cycle(CycleState(**{k: values[k] for k in CycleState.__dataclass_fields__}),
                   field_row[0].area_ha, today)  # fmt: skip
    cycle = CropCycle(**values)
    db.add(cycle)
    db.flush()
    _audit(db, user, "crop_cycle.created", "crop_cycle", cycle.id, rid)
    db.commit()
    return get_cycle(db, user, cycle.id)


def update_cycle(db: Session, user: User, cycle_id: uuid.UUID, data: CropCycleUpdate,
                 rid: str | None, today: date) -> CropCycleOut:  # fmt: skip
    cycle, field, _farm = get_owned_cycle_context(db, user, cycle_id)
    changes = data.model_dump(exclude_unset=True)
    if changes.get("status") is None:
        changes.pop("status", None)  # status cannot be cleared
    merged = {k: changes.get(k, getattr(cycle, k)) for k in CycleState.__dataclass_fields__}
    validate_cycle(CycleState(**merged), field.area_ha, today)
    for key, value in changes.items():
        setattr(cycle, key, value)
    if changes:
        _audit(db, user, "crop_cycle.updated", "crop_cycle", cycle.id, rid, list(changes))
    db.commit()
    return get_cycle(db, user, cycle.id)


def delete_cycle(db: Session, user: User, cycle_id: uuid.UUID, rid: str | None) -> None:
    cycle, _field, _farm = get_owned_cycle_context(db, user, cycle_id)
    _audit(db, user, "crop_cycle.deleted", "crop_cycle", cycle.id, rid)
    db.delete(cycle)
    try:
        db.flush()  # RESTRICT FKs (Crop Doctor cases, expenses, harvests) fail here
    except IntegrityError as e:
        db.rollback()
        raise AppError(
            "cycle_not_empty",
            "This crop cycle has Crop Doctor cases or economics records and cannot be deleted.",
            409,
        ) from e
    db.commit()
