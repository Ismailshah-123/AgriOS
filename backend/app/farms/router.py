"""Farm domain endpoints (flat resources per API_CONTRACTS: /farms, /fields,
/crop-cycles, /crops). Another user's record always answers 404."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.core.pagination import DEFAULT_LIMIT, Cursor, Limit, Page
from app.farms import repository as repo
from app.farms import service
from app.farms.models import CycleStatus
from app.farms.schemas import (
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
from app.identity.deps import CurrentUser, DbSession, RequestId

router = APIRouter()
Search = Annotated[str | None, Query(min_length=1, max_length=80)]


def _today() -> date:
    return date.today()


# ------------------------------------------------------------------------ farms


@router.get("/farms", response_model=Page[FarmOut], tags=["farms"])
def list_farms(user: CurrentUser, db: DbSession, q: Search = None,
               limit: Limit = DEFAULT_LIMIT, cursor: Cursor = None) -> Page[FarmOut]:  # fmt: skip
    return service.list_farms(db, user, q, limit, cursor)


@router.post("/farms", response_model=FarmOut, status_code=status.HTTP_201_CREATED, tags=["farms"])
def create_farm(data: FarmCreate, user: CurrentUser, db: DbSession, rid: RequestId) -> FarmOut:
    return service.create_farm(db, user, data, rid)


@router.get("/farms/{farm_id}", response_model=FarmOut, tags=["farms"])
def get_farm(farm_id: uuid.UUID, user: CurrentUser, db: DbSession) -> FarmOut:
    return service.get_farm(db, user, farm_id)


@router.patch("/farms/{farm_id}", response_model=FarmOut, tags=["farms"])
def update_farm(farm_id: uuid.UUID, data: FarmUpdate, user: CurrentUser, db: DbSession,
                rid: RequestId) -> FarmOut:  # fmt: skip
    return service.update_farm(db, user, farm_id, data, rid)


@router.delete("/farms/{farm_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["farms"])
def delete_farm(farm_id: uuid.UUID, user: CurrentUser, db: DbSession, rid: RequestId) -> None:
    service.delete_farm(db, user, farm_id, rid)


# ----------------------------------------------------------------------- fields


@router.get("/fields", response_model=Page[FieldOut], tags=["fields"])
def list_fields(user: CurrentUser, db: DbSession, farm_id: uuid.UUID | None = None,
                q: Search = None, limit: Limit = DEFAULT_LIMIT, cursor: Cursor = None
                ) -> Page[FieldOut]:  # fmt: skip
    return service.list_fields(db, user, farm_id, q, limit, cursor)


@router.post("/fields", response_model=FieldOut, status_code=status.HTTP_201_CREATED,
             tags=["fields"])  # fmt: skip
def create_field(data: FieldCreate, user: CurrentUser, db: DbSession, rid: RequestId) -> FieldOut:
    return service.create_field(db, user, data, rid)


@router.get("/fields/{field_id}", response_model=FieldOut, tags=["fields"])
def get_field(field_id: uuid.UUID, user: CurrentUser, db: DbSession) -> FieldOut:
    return service.get_field(db, user, field_id)


@router.patch("/fields/{field_id}", response_model=FieldOut, tags=["fields"])
def update_field(field_id: uuid.UUID, data: FieldUpdate, user: CurrentUser, db: DbSession,
                 rid: RequestId) -> FieldOut:  # fmt: skip
    return service.update_field(db, user, field_id, data, rid)


@router.delete("/fields/{field_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["fields"])
def delete_field(field_id: uuid.UUID, user: CurrentUser, db: DbSession, rid: RequestId) -> None:
    service.delete_field(db, user, field_id, rid)


# ------------------------------------------------------------------ crops/cycles


@router.get("/crops", response_model=list[CropOut], tags=["crops"])
def list_crops(_: CurrentUser, db: DbSession) -> list[CropOut]:
    return [CropOut.model_validate(c) for c in repo.list_crops(db)]


@router.get("/crop-cycles", response_model=Page[CropCycleOut], tags=["crop-cycles"])
def list_cycles(user: CurrentUser, db: DbSession, farm_id: uuid.UUID | None = None,
                field_id: uuid.UUID | None = None, status: CycleStatus | None = None,
                crop_id: uuid.UUID | None = None, limit: Limit = DEFAULT_LIMIT,
                cursor: Cursor = None) -> Page[CropCycleOut]:  # fmt: skip
    return service.list_cycles(db, user, limit, cursor, farm_id=farm_id, field_id=field_id,
                               status=status, crop_id=crop_id)  # fmt: skip


@router.post("/crop-cycles", response_model=CropCycleOut, status_code=status.HTTP_201_CREATED,
             tags=["crop-cycles"])  # fmt: skip
def create_cycle(data: CropCycleCreate, user: CurrentUser, db: DbSession,
                 rid: RequestId) -> CropCycleOut:  # fmt: skip
    return service.create_cycle(db, user, data, rid, _today())


@router.get("/crop-cycles/{cycle_id}", response_model=CropCycleOut, tags=["crop-cycles"])
def get_cycle(cycle_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CropCycleOut:
    return service.get_cycle(db, user, cycle_id)


@router.patch("/crop-cycles/{cycle_id}", response_model=CropCycleOut, tags=["crop-cycles"])
def update_cycle(cycle_id: uuid.UUID, data: CropCycleUpdate, user: CurrentUser, db: DbSession,
                 rid: RequestId) -> CropCycleOut:  # fmt: skip
    return service.update_cycle(db, user, cycle_id, data, rid, _today())


@router.delete("/crop-cycles/{cycle_id}", status_code=status.HTTP_204_NO_CONTENT,
               tags=["crop-cycles"])  # fmt: skip
def delete_cycle(cycle_id: uuid.UUID, user: CurrentUser, db: DbSession, rid: RequestId) -> None:
    service.delete_cycle(db, user, cycle_id, rid)
