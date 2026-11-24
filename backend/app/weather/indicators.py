"""Weather-derived agronomic INDICATORS (never diagnoses).

Only rules with a stated basis are evaluated. Anything without a reviewed threshold
source is listed under `not_evaluated` instead of being guessed (MODULE_CONTRACTS s3).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

RULES: dict[str, dict[str, str]] = {
    "frost_risk": {
        "basis": "Air temperature at or below 0 °C (freezing point of water).",
        "source": "Physical definition",
        "review_status": "definition",
    },
    "late_blight_smith_period": {
        "basis": "Smith Period: two consecutive days, each with minimum temperature >= 10 °C "
        "and >= 11 hours with relative humidity >= 90 %.",
        "source": "Smith, L.P. (1956). Potato blight forecasting by 90 per cent humidity "
        "criteria. Plant Pathology 5:83-87.",
        "review_status": "published_criterion_not_locally_validated",
    },
    "rain_vs_et0": {
        "basis": "Forecast rainfall over the next 3 days compared with FAO-56 reference "
        "evapotranspiration (ET0) for the same days (simple water-balance check).",
        "source": "Allen, R.G. et al. (1998). FAO Irrigation and Drainage Paper 56.",
        "review_status": "method_reference; effective rainfall and crop Kc not applied",
    },
    "heavy_rainfall": {
        "basis": "Daily forecast rainfall classified with the India Meteorological Department "
        "24-hour categories: heavy 64.5-115.5 mm, very heavy 115.6-204.4 mm, extremely "
        "heavy >= 204.5 mm.",
        "source": "India Meteorological Department, rainfall intensity terminology "
        "(regional South Asian classification).",
        "review_status": "regional_classification_not_PMD_and_not_crop_specific",
        "limitations": "Grid-cell model rainfall; local convective totals can differ widely.",
    },
    "high_wind": {
        "basis": "Daily maximum 10 m wind speed classified with the Beaufort scale: strong "
        "breeze (force 6) 39-49 km/h, near gale (7) 50-61 km/h, gale (8) >= 62 km/h.",
        "source": "Beaufort wind force scale as used by the World Meteorological Organization.",
        "review_status": "definition",
        "limitations": "Sustained 10 m wind from the forecast model; gusts are not included.",
    },
    "dry_spell": {
        "basis": "Longest run of consecutive forecast days with rainfall < 1 mm (a dry day "
        "in the ETCCDI convention; same definition as the CDD index).",
        "source": "ETCCDI (CCl/CLIVAR/JCOMM Expert Team on Climate Change Detection and "
        "Indices), climate extremes index definitions.",
        "review_status": "definition_no_crop_threshold",
        "limitations": "Reported as information only; no crop-specific drought threshold is "
        "applied. Limited to the forecast horizon.",
    },
    "rainfall_accumulation": {
        "basis": "Sum of daily forecast rainfall over the forecast horizon.",
        "source": "Arithmetic total of provider daily precipitation_sum.",
        "review_status": "definition",
        "limitations": "Gross rainfall, not effective rainfall reaching the root zone.",
    },
}
for _r in ("frost_risk", "late_blight_smith_period", "rain_vs_et0"):
    RULES[_r].setdefault(
        "limitations",
        {
            "frost_risk": "Air temperature at 2 m; ground frost can occur above 0 °C air.",
            "late_blight_smith_period": "Weather criterion only; inoculum and crop state "
            "are unknown. Not a diagnosis.",
            "rain_vs_et0": "Gross rain vs reference ET0; crop Kc and effective rain not applied.",
        }[_r],
    )
IMD_HEAVY = [
    (204.5, "extremely_heavy", "warning"),
    (115.6, "very_heavy", "warning"),
    (64.5, "heavy", "watch"),
]
BEAUFORT = [
    (62.0, "gale_or_stronger", "warning"),
    (50.0, "near_gale", "watch"),
    (39.0, "strong_breeze", "watch"),
]
NOT_EVALUATED = [
    {"indicator": "heat_stress", "reason": "No reviewed crop-specific threshold source yet."},
    {"indicator": "spray_wind_window", "reason": "No reviewed threshold source yet."},
]


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, int | float) else None


def evaluate(fc: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    daily = fc.get("daily", [])

    frost_days = [
        d["date"] for d in daily if (t := _num(d.get("temperature_min_c"))) is not None and t <= 0.0
    ]
    if frost_days:
        out.append(
            {
                "id": "frost_risk",
                "level": "warning",
                "kind": "indicator",
                "message": f"Forecast minimum temperature at or below 0 °C on "
                f"{', '.join(frost_days)}. Protect sensitive crops.",
                "evidence": {"dates": frost_days},
                **RULES["frost_risk"],
            }
        )

    # Smith period over the hourly forecast, grouped by local calendar day.
    by_day: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for h in fc.get("hourly", []):
        if isinstance(h.get("time"), str):
            by_day[h["time"][:10]].append(h)
    qualifying = []
    for day in sorted(by_day):
        hrs = by_day[day]
        temps = [t for h in hrs if (t := _num(h.get("temperature_c"))) is not None]
        humid = sum(1 for h in hrs if (r := _num(h.get("relative_humidity_pct"))) and r >= 90)
        if len(hrs) >= 20 and temps and min(temps) >= 10.0 and humid >= 11:
            qualifying.append(day)
    periods = [d for i, d in enumerate(qualifying[1:], 1) if _consecutive(qualifying[i - 1], d)]
    if periods:
        out.append(
            {
                "id": "late_blight_smith_period",
                "level": "watch",
                "kind": "indicator",
                "message": "Forecast weather meets Smith Period criteria (conditions "
                "conducive to late blight). This is a risk indicator, not a "
                "diagnosis; inspect tomato/potato plants.",
                "evidence": {"qualifying_days": qualifying},
                **RULES["late_blight_smith_period"],
            }
        )

    next3 = daily[:3]
    rain = [_num(d.get("precipitation_sum_mm")) for d in next3]
    et0 = [_num(d.get("et0_fao_mm")) for d in next3]
    if len(next3) == 3 and None not in rain and None not in et0:
        r, e = round(sum(rain), 1), round(sum(et0), 1)  # type: ignore[arg-type]
        if r >= e and r > 0:
            msg = (
                f"Forecast rain ({r} mm) is at least reference ET0 ({e} mm) over 3 days. "
                "Check soil moisture; irrigation may be deferrable."
            )
            level = "info"
        else:
            msg = (
                f"Forecast rain ({r} mm) is below reference ET0 ({e} mm) over 3 days. "
                "Rain alone is unlikely to meet crop water demand."
            )
            level = "info"
        out.append(
            {
                "id": "rain_vs_et0",
                "level": level,
                "kind": "indicator",
                "message": msg,
                "evidence": {"rain_3d_mm": r, "et0_3d_mm": e},
                **RULES["rain_vs_et0"],
            }
        )
    out.extend(_rain_and_wind(daily))
    return out


def _window(dates: list[str]) -> dict[str, str] | None:
    return {"start": min(dates), "end": max(dates)} if dates else None


def _classify(v: float, table: list[tuple[float, str, str]]) -> tuple[str, str] | None:
    return next(((c, lvl) for lim, c, lvl in table if v >= lim), None)


def _rain_and_wind(daily: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    rain = [(d["date"], _num(d.get("precipitation_sum_mm"))) for d in daily if "date" in d]
    heavy = [(day, v, c) for day, v in rain if v is not None and (c := _classify(v, IMD_HEAVY))]
    if heavy:
        level = "warning" if any(c[1] == "warning" for _, _, c in heavy) else "watch"
        out.append(
            {
                "id": "heavy_rainfall",
                "level": level,
                "kind": "indicator",
                "message": "Heavy rainfall forecast: "
                + ", ".join(f"{day} {v} mm ({c[0].replace('_', ' ')})" for day, v, c in heavy)
                + ". Check drainage and avoid field operations that need dry soil.",
                "evidence": {
                    "days": [{"date": d, "rain_mm": v, "category": c[0]} for d, v, c in heavy]
                },
                "time_window": _window([d for d, _, _ in heavy]),
                **RULES["heavy_rainfall"],
            }
        )
    wind = [(d["date"], _num(d.get("wind_speed_max_kmh"))) for d in daily if "date" in d]
    windy = [(day, v, c) for day, v in wind if v is not None and (c := _classify(v, BEAUFORT))]
    if windy:
        level = "warning" if any(c[1] == "warning" for _, _, c in windy) else "watch"
        out.append(
            {
                "id": "high_wind",
                "level": level,
                "kind": "indicator",
                "message": "Strong wind forecast: "
                + ", ".join(f"{day} {v} km/h ({c[0].replace('_', ' ')})" for day, v, c in windy)
                + ". Spraying drift and staking/lodging risk are higher on these days.",
                "evidence": {
                    "days": [
                        {"date": d, "wind_max_kmh": v, "beaufort_class": c[0]} for d, v, c in windy
                    ]
                },
                "time_window": _window([d for d, _, _ in windy]),
                **RULES["high_wind"],
            }
        )
    known = [(d, v) for d, v in rain if v is not None]
    if known and len(known) == len(rain):
        best = run = 0
        for _, v in known:
            run = run + 1 if v < 1.0 else 0
            best = max(best, run)
        dates = [d for d, _ in known]
        out.append(
            {
                "id": "dry_spell",
                "level": "info",
                "kind": "indicator",
                "message": f"Longest run of dry forecast days (< 1 mm): {best} of "
                f"{len(known)} days.",
                "evidence": {"longest_dry_run_days": best, "forecast_days": len(known)},
                "time_window": _window(dates),
                **RULES["dry_spell"],
            }
        )
        total = round(sum(v for _, v in known), 1)
        out.append(
            {
                "id": "rainfall_accumulation",
                "level": "info",
                "kind": "indicator",
                "message": f"Total forecast rainfall over {len(known)} days: {total} mm.",
                "evidence": {"total_rain_mm": total, "forecast_days": len(known)},
                "time_window": _window(dates),
                **RULES["rainfall_accumulation"],
            }
        )
    return out


def _consecutive(a: str, b: str) -> bool:
    from datetime import date

    return (date.fromisoformat(b) - date.fromisoformat(a)).days == 1
