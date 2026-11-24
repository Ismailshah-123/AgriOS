import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.farms.models import CycleStatus, Province, Season
from app.kernel.origin import DataOrigin
from app.units.area import AreaUnit

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Latitude = Annotated[Decimal, Field(ge=-90, le=90)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180)]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ------------------------------------------------------------------------ farms


class FarmCreate(_In):
    name: Name
    province: Province | None = None
    district: ShortText | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def _location_pair(self) -> "FarmCreate":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be given together")
        return self


class FarmUpdate(_In):
    name: Name | None = None
    province: Province | None = None
    district: ShortText | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    notes: Notes | None = None


class FarmOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    province: Province | None
    district: str | None
    latitude: float | None
    longitude: float | None
    location_precision: Literal["0.01_degree"] = "0.01_degree"
    notes: str | None
    field_count: int = 0
    total_area_ha: float = 0.0
    created_at: datetime
    updated_at: datetime


# ----------------------------------------------------------------------- fields


class AreaIn(_In):
    value: Annotated[Decimal, Field(gt=0, le=1_000_000, decimal_places=4)]
    unit: AreaUnit


class AreaOut(BaseModel):
    hectares: float
    value: float
    unit: AreaUnit
    data_origin: DataOrigin


class FieldCreate(_In):
    farm_id: uuid.UUID
    name: Name
    area: AreaIn
    area_origin: Literal[DataOrigin.FARMER_ENTERED, DataOrigin.MEASURED] = DataOrigin.FARMER_ENTERED
    notes: Notes | None = None


class FieldUpdate(_In):
    name: Name | None = None
    area: AreaIn | None = None
    area_origin: Literal[DataOrigin.FARMER_ENTERED, DataOrigin.MEASURED] | None = None
    notes: Notes | None = None


class FieldOut(BaseModel):
    id: uuid.UUID
    farm_id: uuid.UUID
    farm_name: str
    name: str
    area: AreaOut
    notes: str | None
    active_cycle_count: int
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------ crops/cycles


class CropOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    code: str
    name_en: str
    name_ur: str | None
    scientific_name: str | None


class CropCycleCreate(_In):
    field_id: uuid.UUID
    crop_id: uuid.UUID
    variety: Name | None = None
    season: Season | None = None
    status: CycleStatus = CycleStatus.PLANNED
    sowing_date: date | None = None
    expected_harvest_date: date | None = None
    harvest_date: date | None = None
    area_ha: Annotated[Decimal, Field(gt=0, le=100_000, decimal_places=4)] | None = None
    notes: Notes | None = None


class CropCycleUpdate(_In):
    variety: Name | None = None
    season: Season | None = None
    status: CycleStatus | None = None
    sowing_date: date | None = None
    expected_harvest_date: date | None = None
    harvest_date: date | None = None
    area_ha: Annotated[Decimal, Field(gt=0, le=100_000, decimal_places=4)] | None = None
    notes: Notes | None = None


class CropCycleOut(BaseModel):
    id: uuid.UUID
    field_id: uuid.UUID
    field_name: str
    farm_id: uuid.UUID
    farm_name: str
    crop: CropOut
    variety: str | None
    season: Season | None
    status: CycleStatus
    sowing_date: date | None
    expected_harvest_date: date | None
    harvest_date: date | None
    area_ha: float | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
