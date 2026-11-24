"""Economics API shapes. Money and quantities are decimal STRINGS in JSON (no float
rounding); currency is always PKR and named in every response."""

import uuid
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.economics.models import ExpenseCategory

Money = Annotated[Decimal, Field(gt=0, lt=Decimal("1e12"), decimal_places=2)]
Price = Annotated[Decimal, Field(ge=0, lt=Decimal("1e10"), decimal_places=2)]
Kg = Annotated[Decimal, Field(gt=0, lt=Decimal("1e10"), decimal_places=2)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Buyer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


def _not_future(d: date | None, name: str) -> None:
    if d is not None and d > date.today():
        raise ValueError(f"{name} cannot be in the future")


class ExpenseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: ExpenseCategory | None = None
    amount_pkr: Money | None = None
    incurred_on: date | None = None
    note: Note | None = None

    @model_validator(mode="after")
    def _dates(self) -> "ExpenseUpdate":
        _not_future(self.incurred_on, "incurred_on")
        return self


class ExpenseIn(ExpenseUpdate):
    crop_cycle_id: uuid.UUID
    category: ExpenseCategory
    amount_pkr: Money
    incurred_on: date


class HarvestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recorded_on: date | None = None
    quantity_kg: Kg | None = None
    price_pkr_per_kg: Price | None = None  # None = not sold (yet)
    buyer: Buyer | None = None
    note: Note | None = None

    @model_validator(mode="after")
    def _dates(self) -> "HarvestUpdate":
        _not_future(self.recorded_on, "recorded_on")
        return self


class HarvestIn(HarvestUpdate):
    crop_cycle_id: uuid.UUID
    recorded_on: date
    quantity_kg: Kg


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    crop_cycle_id: uuid.UUID
    note: str | None
    currency: Literal["PKR"] = "PKR"
    data_origin: Literal["farmer_entered"] = "farmer_entered"


class ExpenseOut(_Out):
    category: ExpenseCategory
    amount_pkr: Decimal
    incurred_on: date


class HarvestOut(_Out):
    recorded_on: date
    quantity_kg: Decimal
    price_pkr_per_kg: Decimal | None
    buyer: str | None
    revenue_pkr: Decimal | None = None  # quantity x price; None when unsold


class CycleRef(BaseModel):
    id: uuid.UUID
    crop_name: str
    field_name: str
    farm_name: str
    status: str
    area_ha: Decimal | None


class SummaryOut(BaseModel):
    total_cost_pkr: Decimal
    cost_by_category_pkr: dict[str, Decimal]
    harvested_kg: Decimal
    sold_kg: Decimal
    unsold_kg: Decimal
    revenue_pkr: Decimal
    profit_pkr: Decimal
    average_price_pkr_per_kg: Decimal | None
    cost_per_ha_pkr: Decimal | None
    cost_per_acre_pkr: Decimal | None
    break_even_price_pkr_per_kg: Decimal | None
    break_even_yield_kg: Decimal | None


class CycleEconomicsOut(BaseModel):
    cycle: CycleRef
    currency: Literal["PKR"] = "PKR"
    expenses: list[ExpenseOut]
    harvests: list[HarvestOut]
    summary: SummaryOut
    definitions: list[str]
    limitations: list[str]
