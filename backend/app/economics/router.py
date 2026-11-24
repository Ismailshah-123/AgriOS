"""Farm economics (FR10): crop-cycle expenses, harvest/sales and the cycle summary (owner only)."""

import uuid

from fastapi import APIRouter, status

from app.economics import service
from app.economics.models import Expense, HarvestSale
from app.economics.schemas import (
    CycleEconomicsOut,
    ExpenseIn,
    ExpenseOut,
    ExpenseUpdate,
    HarvestIn,
    HarvestOut,
    HarvestUpdate,
)
from app.identity.deps import CurrentUser, DbSession, RequestId

router = APIRouter(tags=["economics"])


@router.get("/crop-cycles/{cycle_id}/economics", response_model=CycleEconomicsOut)
def cycle_economics(cycle_id: uuid.UUID, user: CurrentUser, db: DbSession) -> CycleEconomicsOut:
    return service.cycle_economics(db, user, cycle_id)


@router.post("/expenses", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(data: ExpenseIn, user: CurrentUser, db: DbSession, rid: RequestId) -> ExpenseOut:
    return service.create_expense(db, user, data, rid)


@router.patch("/expenses/{record_id}", response_model=ExpenseOut)
def update_expense(
    record_id: uuid.UUID, data: ExpenseUpdate, user: CurrentUser, db: DbSession, rid: RequestId
) -> ExpenseOut:
    return ExpenseOut.model_validate(service.update(db, user, Expense, record_id, data, rid))


@router.delete("/expenses/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(record_id: uuid.UUID, user: CurrentUser, db: DbSession, rid: RequestId) -> None:
    service.delete(db, user, Expense, record_id, rid)


@router.post("/harvest-sales", response_model=HarvestOut, status_code=status.HTTP_201_CREATED)
def create_harvest(data: HarvestIn, user: CurrentUser, db: DbSession, rid: RequestId) -> HarvestOut:
    return service.create_harvest(db, user, data, rid)


@router.patch("/harvest-sales/{record_id}", response_model=HarvestOut)
def update_harvest(
    record_id: uuid.UUID, data: HarvestUpdate, user: CurrentUser, db: DbSession, rid: RequestId
) -> HarvestOut:
    return service.harvest_out(service.update(db, user, HarvestSale, record_id, data, rid))


@router.delete("/harvest-sales/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_harvest(record_id: uuid.UUID, user: CurrentUser, db: DbSession, rid: RequestId) -> None:
    service.delete(db, user, HarvestSale, record_id, rid)
