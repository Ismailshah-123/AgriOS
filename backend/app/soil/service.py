"""Soil observations: owner-scoped CRUD, interpretation and per-field history/trends.
Another user's record always answers 404; every write is audited in the same transaction."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.errors import AppError
from app.farms import repository as farm_repo
from app.farms.models import CropCycle, CropDefinition, CycleStatus, Farm, Field
from app.identity.models import User
from app.soil.interpret import interpret
from app.soil.models import SoilObservation
from app.soil.schemas import (
    SoilObservationCreate,
    SoilObservationDetail,
    SoilObservationOut,
    SoilObservationUpdate,
    SoilSummary,
    TrendPoint,
)

TREND_MEASURES = (
    "ph",
    "ec_ds_m",
    "organic_matter_pct",
    "organic_carbon_pct",
    "phosphorus_mg_kg",
    "potassium_mg_kg",
)


def _owned_field(db: Session, user: User, field_id: uuid.UUID) -> Field:
    row = farm_repo.get_field_row(db, user.id, field_id)
    if row is None:
        raise AppError("not_found", "Field not found.", 404)
    return row[0]


def _owned_obs(db: Session, user: User, obs_id: uuid.UUID) -> SoilObservation:
    obs = db.scalar(
        select(SoilObservation)
        .join(Field, Field.id == SoilObservation.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .where(SoilObservation.id == obs_id, Farm.owner_id == user.id)
    )
    if obs is None:
        raise AppError("not_found", "Soil observation not found.", 404)
    return obs


def field_crops(db: Session, field_id: uuid.UUID) -> list[str]:
    return sorted(
        set(
            db.scalars(
                select(CropDefinition.code)
                .join(CropCycle, CropCycle.crop_id == CropDefinition.id)
                .where(
                    CropCycle.field_id == field_id,
                    CropCycle.status.in_([CycleStatus.PLANNED, CycleStatus.ACTIVE]),
                )
            )
        )
    )


def detail(db: Session, obs: SoilObservation) -> SoilObservationDetail:
    crops = field_crops(db, obs.field_id)
    base = SoilObservationOut.model_validate(obs).model_dump()
    return SoilObservationDetail(
        **base, interpretation=interpret(obs, crops), crops_considered=crops
    )


def create(
    db: Session, user: User, data: SoilObservationCreate, rid: str | None
) -> SoilObservationDetail:
    _owned_field(db, user, data.field_id)
    obs = SoilObservation(created_by=user.id, **data.model_dump())
    db.add(obs)
    db.flush()
    audit.record(
        db,
        action="soil_observation.created",
        entity="soil_observation",
        entity_id=obs.id,
        actor_id=user.id,
        meta={"field_id": str(obs.field_id), "data_origin": obs.data_origin},
        request_id=rid,
    )
    db.commit()
    db.refresh(obs)
    return detail(db, obs)


def get(db: Session, user: User, obs_id: uuid.UUID) -> SoilObservationDetail:
    return detail(db, _owned_obs(db, user, obs_id))


def list_for_field(db: Session, user: User, field_id: uuid.UUID) -> list[SoilObservationOut]:
    _owned_field(db, user, field_id)
    rows = db.scalars(
        select(SoilObservation)
        .where(SoilObservation.field_id == field_id)
        .order_by(SoilObservation.sampled_on.desc(), SoilObservation.created_at.desc())
    )
    return [SoilObservationOut.model_validate(r) for r in rows]


def update(
    db: Session, user: User, obs_id: uuid.UUID, data: SoilObservationUpdate, rid: str | None
) -> SoilObservationDetail:
    obs = _owned_obs(db, user, obs_id)
    changes = data.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(obs, k, v)
    try:  # re-validate the merged record with the create rules
        SoilObservationCreate.model_validate(
            {
                **SoilObservationOut.model_validate(obs).model_dump(
                    exclude={"id", "created_at", "units"}
                ),
            }
        )
    except ValueError as e:
        db.rollback()
        raise AppError("validation_error", str(e).splitlines()[-1][:300], 422) from e
    audit.record(
        db,
        action="soil_observation.updated",
        entity="soil_observation",
        entity_id=obs.id,
        actor_id=user.id,
        meta={"fields": sorted(changes)},
        request_id=rid,
    )
    db.commit()
    db.refresh(obs)
    return detail(db, obs)


def delete(db: Session, user: User, obs_id: uuid.UUID, rid: str | None) -> None:
    obs = _owned_obs(db, user, obs_id)
    audit.record(
        db,
        action="soil_observation.deleted",
        entity="soil_observation",
        entity_id=obs.id,
        actor_id=user.id,
        meta={"field_id": str(obs.field_id), "sampled_on": obs.sampled_on.isoformat()},
        request_id=rid,
    )
    db.delete(obs)
    db.commit()


def summary(db: Session, user: User, field_id: uuid.UUID) -> SoilSummary:
    field = _owned_field(db, user, field_id)
    rows = list(
        db.scalars(
            select(SoilObservation)
            .where(SoilObservation.field_id == field_id)
            .order_by(SoilObservation.sampled_on, SoilObservation.created_at)
        )
    )
    trends = {
        m: [
            TrendPoint(
                sampled_on=r.sampled_on,
                value=float(getattr(r, m)),
                data_origin=r.data_origin,
                observation_id=r.id,
            )
            for r in rows
            if getattr(r, m) is not None
        ]
        for m in TREND_MEASURES
    }
    return SoilSummary(
        field_id=field.id,
        field_name=field.name,
        observations=len(rows),
        latest=detail(db, rows[-1]) if rows else None,
        trends=trends,
    )
