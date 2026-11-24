"""Owner-scoped queries. Every lookup joins up to `farms.owner_id`, so a record that
belongs to someone else is simply not found (the API then answers 404)."""

import uuid
from typing import Any

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.pagination import paginate
from app.farms.models import CropCycle, CropDefinition, CycleStatus, Farm, Field

# ------------------------------------------------------------------------ farms


def _field_stats() -> Any:
    return (
        select(
            Field.farm_id,
            func.count(Field.id).label("field_count"),
            func.coalesce(func.sum(Field.area_ha), 0).label("total_area_ha"),
        )
        .group_by(Field.farm_id)
        .subquery()
    )


def _farm_query(owner_id: uuid.UUID) -> Select[Any]:
    stats = _field_stats()
    return (
        select(
            Farm,
            func.coalesce(stats.c.field_count, 0),
            func.coalesce(stats.c.total_area_ha, 0),
        )
        .outerjoin(stats, stats.c.farm_id == Farm.id)
        .where(Farm.owner_id == owner_id)
    )


def list_farms(
    db: Session, owner_id: uuid.UUID, q: str | None, limit: int, cursor: str | None
) -> list[Any]:
    stmt = _farm_query(owner_id)
    if q:
        stmt = stmt.where(Farm.name.icontains(q, autoescape=True))
    return list(db.execute(paginate(stmt, Farm, limit, cursor)).all())


def get_farm_row(db: Session, owner_id: uuid.UUID, farm_id: uuid.UUID) -> Any | None:
    return db.execute(_farm_query(owner_id).where(Farm.id == farm_id)).first()


def get_owned_farm(db: Session, owner_id: uuid.UUID, farm_id: uuid.UUID) -> Farm | None:
    return db.scalar(select(Farm).where(Farm.id == farm_id, Farm.owner_id == owner_id))


def farm_name_taken(
    db: Session, owner_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(Farm.id).where(Farm.owner_id == owner_id, func.lower(Farm.name) == name.lower())
    if exclude:
        stmt = stmt.where(Farm.id != exclude)
    return db.scalar(stmt) is not None


def farm_has_fields(db: Session, farm_id: uuid.UUID) -> bool:
    return db.scalar(select(Field.id).where(Field.farm_id == farm_id).limit(1)) is not None


# ----------------------------------------------------------------------- fields


def _active_cycles() -> Any:
    return (
        select(CropCycle.field_id, func.count(CropCycle.id).label("n"))
        .where(CropCycle.status == CycleStatus.ACTIVE)
        .group_by(CropCycle.field_id)
        .subquery()
    )


def _field_query(owner_id: uuid.UUID) -> Select[Any]:
    active = _active_cycles()
    return (
        select(Field, Farm.name, func.coalesce(active.c.n, 0))
        .join(Farm, Farm.id == Field.farm_id)
        .outerjoin(active, active.c.field_id == Field.id)
        .where(Farm.owner_id == owner_id)
    )


def list_fields(
    db: Session,
    owner_id: uuid.UUID,
    farm_id: uuid.UUID | None,
    q: str | None,
    limit: int,
    cursor: str | None,
) -> list[Any]:
    stmt = _field_query(owner_id)
    if farm_id:
        stmt = stmt.where(Field.farm_id == farm_id)
    if q:
        stmt = stmt.where(Field.name.icontains(q, autoescape=True))
    return list(db.execute(paginate(stmt, Field, limit, cursor)).all())


def get_field_row(db: Session, owner_id: uuid.UUID, field_id: uuid.UUID) -> Any | None:
    return db.execute(_field_query(owner_id).where(Field.id == field_id)).first()


def field_name_taken(
    db: Session, farm_id: uuid.UUID, name: str, exclude: uuid.UUID | None = None
) -> bool:
    stmt = select(Field.id).where(Field.farm_id == farm_id, func.lower(Field.name) == name.lower())
    if exclude:
        stmt = stmt.where(Field.id != exclude)
    return db.scalar(stmt) is not None


def field_has_cycles(db: Session, field_id: uuid.UUID) -> bool:
    return (
        db.scalar(select(CropCycle.id).where(CropCycle.field_id == field_id).limit(1)) is not None
    )


# ------------------------------------------------------------------ crops/cycles


def list_crops(db: Session) -> list[CropDefinition]:
    stmt = select(CropDefinition).where(CropDefinition.is_active).order_by(CropDefinition.name_en)
    return list(db.scalars(stmt))


def get_active_crop(db: Session, crop_id: uuid.UUID) -> CropDefinition | None:
    return db.scalar(
        select(CropDefinition).where(CropDefinition.id == crop_id, CropDefinition.is_active)
    )


def _cycle_query(owner_id: uuid.UUID) -> Select[Any]:
    return (
        select(CropCycle, Field, Farm, CropDefinition)
        .join(Field, Field.id == CropCycle.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .join(CropDefinition, CropDefinition.id == CropCycle.crop_id)
        .where(Farm.owner_id == owner_id)
    )


def list_cycles(
    db: Session,
    owner_id: uuid.UUID,
    *,
    farm_id: uuid.UUID | None,
    field_id: uuid.UUID | None,
    status: CycleStatus | None,
    crop_id: uuid.UUID | None,
    limit: int,
    cursor: str | None,
) -> list[Any]:
    stmt = _cycle_query(owner_id)
    if farm_id:
        stmt = stmt.where(Farm.id == farm_id)
    if field_id:
        stmt = stmt.where(Field.id == field_id)
    if status:
        stmt = stmt.where(CropCycle.status == status)
    if crop_id:
        stmt = stmt.where(CropCycle.crop_id == crop_id)
    return list(db.execute(paginate(stmt, CropCycle, limit, cursor)).all())


def get_cycle_row(db: Session, owner_id: uuid.UUID, cycle_id: uuid.UUID) -> Any | None:
    return db.execute(_cycle_query(owner_id).where(CropCycle.id == cycle_id)).first()
