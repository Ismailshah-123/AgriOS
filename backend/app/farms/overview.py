"""Farm-domain overview for the dashboard: real counts and the farmer's own dates.

Nothing here is estimated or generated. "Upcoming" items come only from dates the
farmer entered on crop cycles (planned sowing, expected harvest).
"""

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.farms.models import CropCycle, CropDefinition, CycleStatus, Farm, Field

UPCOMING_WINDOW_DAYS = 60


def counts(db: Session, owner_id: uuid.UUID) -> dict[str, Any]:
    farms = db.scalar(select(func.count(Farm.id)).where(Farm.owner_id == owner_id)) or 0
    field_count, area = db.execute(
        select(func.count(Field.id), func.coalesce(func.sum(Field.area_ha), 0))
        .join(Farm, Farm.id == Field.farm_id)
        .where(Farm.owner_id == owner_id)
    ).one()
    by_status = dict(
        db.execute(
            select(CropCycle.status, func.count(CropCycle.id))
            .join(Field, Field.id == CropCycle.field_id)
            .join(Farm, Farm.id == Field.farm_id)
            .where(Farm.owner_id == owner_id)
            .group_by(CropCycle.status)
        ).all()
    )
    return {
        "farms": farms,
        "fields": field_count,
        "total_area_ha": float(area),
        "cycles_by_status": {s.value: by_status.get(s, 0) for s in CycleStatus},
    }


def _cycles(owner_id: uuid.UUID) -> Any:
    return (
        select(CropCycle, Field.name, Farm.name, CropDefinition.name_en)
        .join(Field, Field.id == CropCycle.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .join(CropDefinition, CropDefinition.id == CropCycle.crop_id)
        .where(Farm.owner_id == owner_id)
    )


def _cycle_brief(row: Any) -> dict[str, Any]:
    cycle, field_name, farm_name, crop_name = row
    return {
        "id": cycle.id,
        "crop_name": crop_name,
        "variety": cycle.variety,
        "field_name": field_name,
        "farm_name": farm_name,
        "status": cycle.status,
        "sowing_date": cycle.sowing_date,
        "expected_harvest_date": cycle.expected_harvest_date,
    }


def active_cycles(db: Session, owner_id: uuid.UUID, limit: int = 6) -> list[dict[str, Any]]:
    stmt = (
        _cycles(owner_id)
        .where(CropCycle.status == CycleStatus.ACTIVE)
        .order_by(CropCycle.sowing_date.desc().nulls_last(), CropCycle.id)
        .limit(limit)
    )
    return [_cycle_brief(r) for r in db.execute(stmt).all()]


def upcoming(db: Session, owner_id: uuid.UUID, today: date, limit: int = 6) -> list[dict[str, Any]]:
    horizon = today + timedelta(days=UPCOMING_WINDOW_DAYS)
    sowings = _cycles(owner_id).where(
        CropCycle.status == CycleStatus.PLANNED,
        CropCycle.sowing_date.between(today, horizon),
    )
    harvests = _cycles(owner_id).where(
        CropCycle.status == CycleStatus.ACTIVE,
        CropCycle.expected_harvest_date.between(today, horizon),
    )
    items = [
        {"kind": "planned_sowing", "date": r[0].sowing_date, "cycle": _cycle_brief(r)}
        for r in db.execute(sowings).all()
    ] + [
        {"kind": "expected_harvest", "date": r[0].expected_harvest_date, "cycle": _cycle_brief(r)}
        for r in db.execute(harvests).all()
    ]
    return sorted(items, key=lambda i: (i["date"], str(i["cycle"]["id"])))[:limit]


def names_for(
    db: Session, owner_id: uuid.UUID, refs: list[tuple[str, uuid.UUID]]
) -> dict[uuid.UUID, str]:
    """Current display names for audit references that still exist (owner-scoped)."""
    ids = {kind: [i for k, i in refs if k == kind] for kind in ("farm", "field", "crop_cycle")}
    names: dict[uuid.UUID, str] = {}
    if ids["farm"]:
        q = select(Farm.id, Farm.name).where(Farm.owner_id == owner_id, Farm.id.in_(ids["farm"]))
        names.update(dict(db.execute(q).all()))
    if ids["field"]:
        q = (
            select(Field.id, Field.name)
            .join(Farm, Farm.id == Field.farm_id)
            .where(Farm.owner_id == owner_id, Field.id.in_(ids["field"]))
        )
        names.update(dict(db.execute(q).all()))
    if ids["crop_cycle"]:
        q = (
            select(CropCycle.id, CropDefinition.name_en + " on " + Field.name)
            .join(Field, Field.id == CropCycle.field_id)
            .join(Farm, Farm.id == Field.farm_id)
            .join(CropDefinition, CropDefinition.id == CropCycle.crop_id)
            .where(Farm.owner_id == owner_id, CropCycle.id.in_(ids["crop_cycle"]))
        )
        names.update(dict(db.execute(q).all()))
    return names
