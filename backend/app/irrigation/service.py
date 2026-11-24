"""Field crop water demand (ETc) from the field's active crop cycle and forecast ET0.

Estimated demand only (data_origin "inferred"). It is never presented as measured soil
moisture, never converted into an irrigation command, and effective rainfall is not
subtracted (no defensible method/inputs are configured; gross forecast rain is shown
separately). Missing inputs are reported in `missing_information`, never filled.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.farms import repository as farm_repo
from app.farms.models import CropCycle, CropDefinition, CycleStatus
from app.identity.models import User
from app.irrigation import kc
from app.weather import service as weather_service
from app.weather.provider import WeatherProvider

LIMITATIONS = [
    "Kc values are FAO-56 general guidance, not calibrated for Pakistan and not "
    "climate-adjusted for local humidity and wind.",
    "Stage dates assume the crop cycle's sowing date is the FAO-56 planting date "
    "(for transplanted tomato, enter the transplanting date).",
    "Effective rainfall is not subtracted; forecast rain is shown as gross rain only.",
    "This is estimated crop water demand, not measured soil moisture. No equipment is controlled.",
]


def active_cycle(db: Session, field_id: uuid.UUID) -> tuple[CropCycle, str] | None:
    row = db.execute(
        select(CropCycle, CropDefinition.code)
        .join(CropDefinition, CropDefinition.id == CropCycle.crop_id)
        .where(CropCycle.field_id == field_id, CropCycle.status == CycleStatus.ACTIVE)
        .order_by(CropCycle.sowing_date.desc().nulls_last(), CropCycle.created_at.desc())
    ).first()
    return (row[0], row[1]) if row else None


def water_demand(
    db: Session,
    user: User,
    field_id: uuid.UUID,
    provider: WeatherProvider | None,
    today: date | None = None,
) -> dict[str, Any]:
    if farm_repo.get_field_row(db, user.id, field_id) is None:
        raise AppError("not_found", "Field not found.", 404)
    today = today or date.today()
    missing: list[str] = []
    out: dict[str, Any] = {
        "field_id": str(field_id),
        "status": "unavailable",
        "data_origin": "inferred",
        "units": {"et0": "mm/day", "etc": "mm/day", "rain": "mm"},
        "method": "ETc = Kc x ET0 (FAO-56 single crop coefficient)",
        "source": kc.FAO56,
        "crop": None,
        "planting_date": None,
        "days_after_planting": None,
        "current_stage": None,
        "daily": [],
        "totals": None,
        "effective_rainfall": "not_applied",
        "soil_moisture": "not_measured",
        "weather_status": None,
        "weather_retrieved_at": None,
        "missing_information": missing,
        "limitations": LIMITATIONS,
    }
    cyc = active_cycle(db, field_id)
    if cyc is None:
        missing.append("active_crop_cycle")
        return out
    cycle, code = cyc
    out["crop"] = code
    crop = kc.CROPS.get(code)
    if crop is None:
        missing.append(f"kc_table_for_crop:{code}")
    else:
        out["stage_source"] = crop.stage_source
        out["review_status"] = crop.review_status
    if cycle.sowing_date is None:
        missing.append("crop_cycle.sowing_date")
    else:
        out["planting_date"] = cycle.sowing_date.isoformat()
        dap = (today - cycle.sowing_date).days
        out["days_after_planting"] = dap
        if crop is not None:
            k = kc.kc_for_day(crop, dap)
            out["current_stage"] = k[0] if k else "outside_fao56_season"
    weather = weather_service.get_weather(db, user, provider, field_id=field_id)
    out["weather_status"] = weather.status
    out["weather_retrieved_at"] = weather.retrieved_at
    if weather.status == "unavailable":
        missing.append(f"weather:{weather.reason}")
    if missing:
        return out
    daily = [d.model_dump() for d in weather.daily]
    rows = kc.etc_series(crop, cycle.sowing_date, daily)  # type: ignore[arg-type]
    usable = [r for r in rows if r["etc_low_mm"] is not None]
    out["daily"] = rows
    out["status"] = "ok" if usable else "unavailable"
    if not usable:
        missing.append("forecast_days_with_et0_inside_season")
        return out
    rain = [r["rain_mm"] for r in usable]
    out["totals"] = {
        "days": len(usable),
        "et0_mm": round(sum(r["et0_mm"] for r in usable), 1),
        "etc_low_mm": round(sum(r["etc_low_mm"] for r in usable), 1),
        "etc_high_mm": round(sum(r["etc_high_mm"] for r in usable), 1),
        "gross_rain_mm": round(sum(rain), 1) if None not in rain else None,
    }
    return out
