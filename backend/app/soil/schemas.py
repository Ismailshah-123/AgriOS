import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.soil.models import EcMethod, PhMethod, PMethod, Texture

Short = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Ref = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)]
Pct = Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)]
NutrientMeasure = Literal[
    "calcium_mg_kg",
    "magnesium_mg_kg",
    "sulfur_mg_kg",
    "zinc_mg_kg",
    "iron_mg_kg",
    "boron_mg_kg",
    "cec_cmol_kg",
    "nitrogen_total_pct",
    "potassium_mg_kg",
    "organic_carbon_pct",
]
MEASURES = (
    "ph",
    "ec_ds_m",
    "organic_matter_pct",
    "organic_carbon_pct",
    "nitrogen_total_pct",
    "phosphorus_mg_kg",
    "potassium_mg_kg",
    "calcium_mg_kg",
    "magnesium_mg_kg",
    "sulfur_mg_kg",
    "zinc_mg_kg",
    "iron_mg_kg",
    "boron_mg_kg",
    "cec_cmol_kg",
    "texture",
)


class _Fields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    lab_name: Short | None = None
    lab_reference: Ref | None = None
    depth_from_cm: Annotated[Decimal, Field(ge=0, le=500)] | None = None
    depth_to_cm: Annotated[Decimal, Field(gt=0, le=500)] | None = None
    ph: Annotated[Decimal, Field(ge=0, le=14, decimal_places=2)] | None = None
    ph_method: PhMethod = PhMethod.UNKNOWN
    ec_ds_m: Annotated[Decimal, Field(ge=0, le=200, decimal_places=3)] | None = None
    ec_method: EcMethod = EcMethod.UNKNOWN
    organic_matter_pct: Pct | None = None
    organic_carbon_pct: Annotated[Decimal, Field(ge=0, le=60, decimal_places=2)] | None = None
    nitrogen_total_pct: Annotated[Decimal, Field(ge=0, le=10, decimal_places=3)] | None = None
    phosphorus_mg_kg: Annotated[Decimal, Field(ge=0, le=5000, decimal_places=2)] | None = None
    phosphorus_method: PMethod = PMethod.UNKNOWN
    potassium_mg_kg: Annotated[Decimal, Field(ge=0, le=10000, decimal_places=2)] | None = None
    calcium_mg_kg: Annotated[Decimal, Field(ge=0, le=20000, decimal_places=2)] | None = None
    magnesium_mg_kg: Annotated[Decimal, Field(ge=0, le=10000, decimal_places=2)] | None = None
    sulfur_mg_kg: Annotated[Decimal, Field(ge=0, le=5000, decimal_places=2)] | None = None
    zinc_mg_kg: Annotated[Decimal, Field(ge=0, le=1000, decimal_places=3)] | None = None
    iron_mg_kg: Annotated[Decimal, Field(ge=0, le=5000, decimal_places=3)] | None = None
    boron_mg_kg: Annotated[Decimal, Field(ge=0, le=500, decimal_places=3)] | None = None
    cec_cmol_kg: Annotated[Decimal, Field(ge=0, le=200, decimal_places=2)] | None = None
    nutrient_methods: dict[NutrientMeasure, Short] | None = None  # lab method label per measure
    texture: Texture | None = None
    notes: Notes | None = None


class SoilObservationCreate(_Fields):
    field_id: uuid.UUID
    sampled_on: date
    data_origin: Literal["measured", "farmer_entered"]

    @model_validator(mode="after")
    def _rules(self) -> "SoilObservationCreate":
        if self.sampled_on > date.today():
            raise ValueError("sampled_on cannot be in the future")
        if all(getattr(self, m) is None for m in MEASURES):
            raise ValueError("enter at least one measured value")
        if self.data_origin == "measured" and not self.lab_name:
            raise ValueError("laboratory results need lab_name (else use farmer_entered)")
        if (
            self.depth_from_cm is not None
            and self.depth_to_cm is not None
            and self.depth_to_cm <= self.depth_from_cm
        ):
            raise ValueError("depth_to_cm must be greater than depth_from_cm")
        return self


class SoilObservationUpdate(_Fields):
    sampled_on: date | None = None
    data_origin: Literal["measured", "farmer_entered"] | None = None


class SoilObservationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    field_id: uuid.UUID
    sampled_on: date
    data_origin: str
    lab_name: str | None
    lab_reference: str | None
    depth_from_cm: float | None
    depth_to_cm: float | None
    ph: float | None
    ph_method: PhMethod
    ec_ds_m: float | None
    ec_method: EcMethod
    organic_matter_pct: float | None
    organic_carbon_pct: float | None
    nitrogen_total_pct: float | None
    phosphorus_mg_kg: float | None
    phosphorus_method: PMethod
    potassium_mg_kg: float | None
    calcium_mg_kg: float | None
    magnesium_mg_kg: float | None
    sulfur_mg_kg: float | None
    zinc_mg_kg: float | None
    iron_mg_kg: float | None
    boron_mg_kg: float | None
    cec_cmol_kg: float | None
    nutrient_methods: dict[str, str] | None
    texture: Texture | None
    notes: str | None
    created_at: datetime
    units: dict[str, str] = {
        "ph": "pH units",
        "ec_ds_m": "dS/m",
        "organic_matter_pct": "% (organic matter)",
        "organic_carbon_pct": "% (organic carbon)",
        "nitrogen_total_pct": "% total N",
        "phosphorus_mg_kg": "mg/kg",
        "potassium_mg_kg": "mg/kg",
        "calcium_mg_kg": "mg/kg (exchangeable Ca)",
        "magnesium_mg_kg": "mg/kg (exchangeable Mg)",
        "sulfur_mg_kg": "mg/kg (available S)",
        "zinc_mg_kg": "mg/kg (available Zn)",
        "iron_mg_kg": "mg/kg (available Fe)",
        "boron_mg_kg": "mg/kg (available B)",
        "cec_cmol_kg": "cmol(+)/kg",
        "depth": "cm",
    }


class Interpretation(BaseModel):
    flags: list[dict[str, Any]]
    not_evaluated: list[dict[str, str]]
    warnings: list[dict[str, Any]]
    dose_policy: str


class SoilObservationDetail(SoilObservationOut):
    interpretation: Interpretation
    crops_considered: list[str]


class TrendPoint(BaseModel):
    sampled_on: date
    value: float
    data_origin: str
    observation_id: uuid.UUID


class SoilSummary(BaseModel):
    field_id: uuid.UUID
    field_name: str
    observations: int
    latest: SoilObservationDetail | None
    trends: dict[str, list[TrendPoint]]
