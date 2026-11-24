"""FAO-56 single crop coefficient curve and ETc = Kc x ET0 (pure functions, no I/O).

Source: Allen, R.G., Pereira, L.S., Raes, D. & Smith, M. (1998). Crop evapotranspiration:
guidelines for computing crop water requirements. FAO Irrigation and Drainage Paper 56.
  - Eq. 56: ETc = Kc x ET0.
  - Fig. 25 / Eq. 66: Kc is constant in the initial and mid-season stages and changes
    linearly through the development and late-season stages.
  - Table 11: stage lengths (days). Table 12: Kc_ini, Kc_mid, Kc_end.
Values are GENERAL international guidance transcribed from FAO-56, not calibrated for
Pakistan, and Kc_mid/Kc_end are NOT climate-adjusted (Eq. 62/65 need RHmin and wind,
which are not applied). Where FAO-56 gives a range, the range is carried through as
low/high instead of choosing a single value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

FAO56 = (
    "Allen, R.G., Pereira, L.S., Raes, D. & Smith, M. (1998). FAO Irrigation and "
    "Drainage Paper 56, Eq. 56, Fig. 25, Tables 11-12."
)


@dataclass(frozen=True)
class CropKc:
    kc_ini: tuple[float, float]
    kc_mid: tuple[float, float]
    kc_end: tuple[float, float]
    stages: tuple[int, int, int, int]  # initial, development, mid-season, late-season (days)
    stage_source: str
    review_status: str = "transcribed_from_FAO56_pending_expert_review"


CROPS: dict[str, CropKc] = {
    "tomato": CropKc(
        kc_ini=(0.60, 0.60),
        kc_mid=(1.15, 1.15),
        kc_end=(0.70, 0.90),
        stages=(30, 40, 40, 25),
        stage_source="FAO-56 Table 11, tomato, arid region, January planting",
    ),
    "cotton": CropKc(
        kc_ini=(0.35, 0.35),
        kc_mid=(1.15, 1.20),
        kc_end=(0.50, 0.70),
        stages=(30, 50, 60, 55),
        stage_source="FAO-56 Table 11, cotton, March-May planting (Egypt; Pakistan; California)",
    ),
}

STAGES = ("initial", "development", "mid_season", "late_season")


def _lerp(a: tuple[float, float], b: tuple[float, float], f: float) -> tuple[float, float]:
    return (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)


def kc_for_day(crop: CropKc, days_after_planting: int) -> tuple[str, float, float] | None:
    """(stage, kc_low, kc_high) for a day after planting; None before planting or after
    the FAO-56 season length (the curve is undefined there, so nothing is estimated).

    Eq. 66 counts season days i = 1 .. length with the planting day as i = 1, so
    i = days_after_planting + 1 (checked against FAO-56 Example 28)."""
    d = days_after_planting
    i = d + 1
    l1, l2, l3, l4 = crop.stages
    if d < 0 or d >= l1 + l2 + l3 + l4:
        return None
    if d < l1:
        kc, stage = crop.kc_ini, "initial"
    elif d < l1 + l2:
        kc, stage = _lerp(crop.kc_ini, crop.kc_mid, (i - l1) / l2), "development"
    elif d < l1 + l2 + l3:
        kc, stage = crop.kc_mid, "mid_season"
    else:
        kc, stage = _lerp(crop.kc_mid, crop.kc_end, (i - l1 - l2 - l3) / l4), "late_season"
    lo, hi = sorted((round(kc[0], 3), round(kc[1], 3)))
    return stage, lo, hi


def etc_series(crop: CropKc, planting: date, daily: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per forecast day: Kc range and ETc range (mm/day). Days with missing ET0 or outside
    the season keep None values (never filled)."""
    out = []
    for day in daily:
        d = date.fromisoformat(day["date"])
        et0 = day.get("et0_fao_mm")
        k = kc_for_day(crop, (d - planting).days)
        row: dict[str, Any] = {
            "date": day["date"],
            "stage": k[0] if k else None,
            "kc_low": k[1] if k else None,
            "kc_high": k[2] if k else None,
            "et0_mm": et0,
            "etc_low_mm": None,
            "etc_high_mm": None,
            "rain_mm": day.get("precipitation_sum_mm"),
        }
        if k and isinstance(et0, int | float):
            row["etc_low_mm"] = round(k[1] * et0, 2)
            row["etc_high_mm"] = round(k[2] * et0, 2)
        out.append(row)
    return out
