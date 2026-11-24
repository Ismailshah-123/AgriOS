from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel


class WeatherLocation(BaseModel):
    farm_id: str
    farm_name: str
    field_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    precision: Literal["0.01_degree"] = "0.01_degree"


class CurrentWeather(BaseModel):
    time: str | None
    temperature_c: float | None
    relative_humidity_pct: float | None
    precipitation_mm: float | None
    wind_speed_kmh: float | None
    weather_code: int | None


class HourlyWeather(BaseModel):
    time: str
    temperature_c: float | None
    relative_humidity_pct: float | None
    precipitation_mm: float | None
    precipitation_probability_pct: float | None


class DailyWeather(BaseModel):
    date: str
    temperature_max_c: float | None
    temperature_min_c: float | None
    precipitation_sum_mm: float | None
    precipitation_probability_max_pct: float | None
    wind_speed_max_kmh: float | None
    et0_fao_mm: float | None


class Indicator(BaseModel):
    id: str
    level: Literal["info", "watch", "warning"]
    kind: Literal["indicator"] = "indicator"
    message: str
    basis: str
    source: str
    review_status: str
    limitations: str | None = None
    time_window: dict[str, str] | None = None
    evidence: dict[str, Any]


class WeatherOut(BaseModel):
    status: Literal["fresh", "stale", "unavailable"]
    reason: str | None = None
    data_origin: Literal["retrieved"] = "retrieved"
    location: WeatherLocation
    provider: dict[str, str] | None = None
    retrieved_at: datetime | None = None
    age_minutes: int | None = None
    timezone: str | None = None
    units: dict[str, str] = {
        "temperature": "°C",
        "humidity": "%",
        "precipitation": "mm",
        "wind_speed": "km/h",
        "et0": "mm/day",
    }
    current: CurrentWeather | None = None
    hourly: list[HourlyWeather] = []
    daily: list[DailyWeather] = []
    indicators: list[Indicator] = []
    not_evaluated: list[dict[str, str]] = []
    disclaimer: str = (
        "Forecasts are model estimates for a ~1 km grid cell, not on-farm measurements. "
        "Indicators describe weather conditions only; they are not disease diagnoses."
    )
