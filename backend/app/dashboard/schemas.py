import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.farms.models import CycleStatus


class OverviewCounts(BaseModel):
    farms: int
    fields: int
    total_area_ha: float
    cycles_by_status: dict[CycleStatus, int]


class CycleBrief(BaseModel):
    id: uuid.UUID
    crop_name: str
    variety: str | None
    field_name: str
    farm_name: str
    status: CycleStatus
    sowing_date: date | None
    expected_harvest_date: date | None


class UpcomingItem(BaseModel):
    kind: Literal["planned_sowing", "expected_harvest"]
    date: date
    source: Literal["farmer_entered"] = "farmer_entered"
    cycle: CycleBrief


class RecentChange(BaseModel):
    action: str
    entity: Literal["farm", "field", "crop_cycle"]
    entity_id: uuid.UUID | None
    name: str | None  # None when the record has since been deleted
    created_at: datetime


class CropHealthBrief(BaseModel):
    cases: int
    awaiting_analysis: int
    needs_follow_up: int
    model_availability: str


class SoilBrief(BaseModel):
    observations: int
    fields_with_tests: int
    latest_sampled_on: date | None


class WeatherBrief(BaseModel):
    farms: int
    farms_with_location: int


class IrrigationBrief(BaseModel):
    growing_cycles: int
    cycles_with_estimate: int


class AgentsBrief(BaseModel):
    runs: int
    pending_approvals: int


class IntelligenceSummary(BaseModel):
    crop_health: CropHealthBrief
    soil: SoilBrief
    weather: WeatherBrief
    irrigation: IrrigationBrief
    agents: AgentsBrief


class OverviewOut(BaseModel):
    counts: OverviewCounts
    active_cycles: list[CycleBrief]
    upcoming: list[UpcomingItem]
    recent_changes: list[RecentChange]
    intelligence: IntelligenceSummary


class AreaByCrop(BaseModel):
    crop: str
    cycles: int
    area_ha: float


class CasesByMonth(BaseModel):
    month: str  # YYYY-MM
    cases: int


class CaseAnalytics(BaseModel):
    by_status: dict[str, int]
    by_month: list[CasesByMonth]


class CycleEconomicsBrief(BaseModel):
    crop_cycle_id: uuid.UUID
    crop: str
    field: str
    cost_pkr: Decimal
    revenue_pkr: Decimal
    profit_pkr: Decimal


class EconomicsAnalytics(BaseModel):
    currency: Literal["PKR"]
    total_cost_pkr: Decimal
    total_revenue_pkr: Decimal
    profit_pkr: Decimal
    cost_by_category_pkr: dict[str, Decimal]
    cycles: list[CycleEconomicsBrief]


class AnalyticsOut(BaseModel):
    generated_at: datetime
    area_by_crop: list[AreaByCrop]
    cases: CaseAnalytics
    pending_expert_reviews: int
    economics: EconomicsAnalytics
