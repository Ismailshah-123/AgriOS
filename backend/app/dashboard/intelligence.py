"""Owner-scoped intelligence summary for the dashboard.

Counts only what is stored or deterministically available: no forecast values, no
estimates. Weather availability = farms with a stored location; ETc availability =
growing cycles whose crop has a cited FAO-56 Kc table.
"""

import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.models import ActionStatus, AgentAction, AgentRun
from app.crop_health import queries as case_queries
from app.farms.models import CropCycle, CropDefinition, CycleStatus, Farm, Field
from app.irrigation.kc import CROPS
from app.soil.models import SoilObservation


def _soil(db: Session, owner_id: uuid.UUID) -> dict[str, Any]:
    n, fields, latest = db.execute(
        select(
            func.count(SoilObservation.id),
            func.count(func.distinct(SoilObservation.field_id)),
            func.max(SoilObservation.sampled_on),
        )
        .join(Field, Field.id == SoilObservation.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .where(Farm.owner_id == owner_id)
    ).one()
    return {"observations": n, "fields_with_tests": fields, "latest_sampled_on": latest}


def _weather(db: Session, owner_id: uuid.UUID) -> dict[str, Any]:
    total, located = db.execute(
        select(func.count(Farm.id), func.count(Farm.latitude)).where(Farm.owner_id == owner_id)
    ).one()
    return {"farms": total, "farms_with_location": located}


def _irrigation(db: Session, owner_id: uuid.UUID) -> dict[str, Any]:
    codes = db.scalars(
        select(CropDefinition.code)
        .join(CropCycle, CropCycle.crop_id == CropDefinition.id)
        .join(Field, Field.id == CropCycle.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .where(Farm.owner_id == owner_id, CropCycle.status == CycleStatus.ACTIVE)
    ).all()  # active cycles always carry a sowing date (crop-cycle rule)
    return {"growing_cycles": len(codes), "cycles_with_estimate": sum(c in CROPS for c in codes)}


def _agents(db: Session, owner_id: uuid.UUID) -> dict[str, Any]:
    runs = db.scalar(select(func.count(AgentRun.id)).where(AgentRun.user_id == owner_id))
    pending = db.scalar(
        select(func.count(AgentAction.id)).where(
            AgentAction.user_id == owner_id, AgentAction.status == ActionStatus.PENDING
        )
    )
    return {"runs": runs or 0, "pending_approvals": pending or 0}


def summary(db: Session, owner_id: uuid.UUID, model_root: Path) -> dict[str, Any]:
    stats = case_queries.stats(db, owner_id, model_root)
    return {
        "crop_health": {
            "cases": stats.total,
            "awaiting_analysis": stats.awaiting_analysis,
            "needs_follow_up": stats.needs_follow_up,
            "model_availability": stats.model_availability,
        },
        "soil": _soil(db, owner_id),
        "weather": _weather(db, owner_id),
        "irrigation": _irrigation(db, owner_id),
        "agents": _agents(db, owner_id),
    }
