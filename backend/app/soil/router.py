"""Soil observations (API_CONTRACTS: CRUD /soil-observations; owner only)."""

import uuid

from fastapi import APIRouter, status

from app.identity.deps import CurrentUser, DbSession, RequestId
from app.soil import service
from app.soil.schemas import (
    SoilObservationCreate,
    SoilObservationDetail,
    SoilObservationOut,
    SoilObservationUpdate,
    SoilSummary,
)

router = APIRouter(tags=["soil"])


@router.get("/soil-observations", response_model=list[SoilObservationOut])
def list_observations(
    field_id: uuid.UUID, user: CurrentUser, db: DbSession
) -> list[SoilObservationOut]:
    return service.list_for_field(db, user, field_id)


@router.post(
    "/soil-observations", response_model=SoilObservationDetail, status_code=status.HTTP_201_CREATED
)
def create_observation(
    data: SoilObservationCreate, user: CurrentUser, db: DbSession, rid: RequestId
) -> SoilObservationDetail:
    return service.create(db, user, data, rid)


@router.get("/soil-observations/{obs_id}", response_model=SoilObservationDetail)
def get_observation(obs_id: uuid.UUID, user: CurrentUser, db: DbSession) -> SoilObservationDetail:
    return service.get(db, user, obs_id)


@router.patch("/soil-observations/{obs_id}", response_model=SoilObservationDetail)
def update_observation(
    obs_id: uuid.UUID, data: SoilObservationUpdate, user: CurrentUser, db: DbSession, rid: RequestId
) -> SoilObservationDetail:
    return service.update(db, user, obs_id, data, rid)


@router.delete("/soil-observations/{obs_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_observation(obs_id: uuid.UUID, user: CurrentUser, db: DbSession, rid: RequestId) -> None:
    service.delete(db, user, obs_id, rid)


@router.get("/fields/{field_id}/soil-summary", response_model=SoilSummary)
def soil_summary(field_id: uuid.UUID, user: CurrentUser, db: DbSession) -> SoilSummary:
    return service.summary(db, user, field_id)
