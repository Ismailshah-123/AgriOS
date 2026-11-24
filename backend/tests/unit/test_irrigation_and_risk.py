"""FAO-56 Kc curve / ETc and the Phase 4B weather risk indicators (pure functions)."""

from datetime import date

from app.irrigation import kc
from app.weather import indicators
from app.weather.provider import normalise_open_meteo
from tests.weather_fixtures import open_meteo_raw

TOMATO = kc.CROPS["tomato"]  # stages 30/40/40/25, Kc 0.60 / 1.15 / 0.70-0.90


def test_kc_curve_stages_and_linear_interpolation() -> None:
    assert kc.kc_for_day(TOMATO, 0) == ("initial", 0.6, 0.6)
    assert kc.kc_for_day(TOMATO, 29) == ("initial", 0.6, 0.6)
    # halfway through development, FAO day i = 50 (d = 49, Eq. 66 i = d + 1; see
    # test_fao56_examples.py): 0.60 + (50 - 30) / 40 * (1.15 - 0.60) = 0.875
    assert kc.kc_for_day(TOMATO, 49) == ("development", 0.875, 0.875)
    assert kc.kc_for_day(TOMATO, 70) == ("mid_season", 1.15, 1.15)
    stage, lo, hi = kc.kc_for_day(TOMATO, 122)  # type: ignore[misc]
    assert stage == "late_season" and lo < hi  # FAO-56 Kc_end range carried through
    assert kc.kc_for_day(TOMATO, -1) is None and kc.kc_for_day(TOMATO, 135) is None


def test_etc_is_kc_times_et0_and_missing_et0_stays_none() -> None:
    daily = [
        {"date": "2026-03-12", "et0_fao_mm": 4.0, "precipitation_sum_mm": 0.0},
        {"date": "2026-03-13", "et0_fao_mm": None, "precipitation_sum_mm": 1.0},
    ]
    rows = kc.etc_series(TOMATO, date(2026, 2, 10), daily)  # day 30 and 31: development
    k = kc.kc_for_day(TOMATO, 30)
    assert rows[0]["etc_low_mm"] == round(k[1] * 4.0, 2)  # type: ignore[index]
    assert rows[1]["etc_low_mm"] is None and rows[1]["kc_low"] is not None


def _fc(**kw: object) -> dict:
    return normalise_open_meteo(open_meteo_raw(**kw))  # type: ignore[arg-type]


def test_heavy_rain_uses_imd_categories_with_window_and_source() -> None:
    fc = _fc(rain=70.0)
    ind = {i["id"]: i for i in indicators.evaluate(fc)}
    heavy = ind["heavy_rainfall"]
    assert heavy["level"] == "watch" and heavy["evidence"]["days"][0]["category"] == "heavy"
    assert heavy["time_window"] == {"start": "2026-11-23", "end": "2026-11-29"}
    assert "India Meteorological Department" in heavy["source"] and heavy["limitations"]
    assert {i["id"] for i in indicators.evaluate(_fc(rain=2.0))}.isdisjoint({"heavy_rainfall"})
    very = {i["id"]: i for i in indicators.evaluate(_fc(rain=120.0))}["heavy_rainfall"]
    assert very["level"] == "warning"


def test_high_wind_beaufort_and_dry_spell_and_accumulation() -> None:
    raw = open_meteo_raw(rain=0.0)
    raw["daily"]["wind_speed_10m_max"] = [12.0, 45.0, 65.0, 10.0, 10.0, 10.0, 10.0]
    raw["daily"]["precipitation_sum"] = [0.0, 0.0, 3.0, 0.0, 0.0, 0.0, 0.5]
    ind = {i["id"]: i for i in indicators.evaluate(normalise_open_meteo(raw))}
    wind = ind["high_wind"]
    assert wind["level"] == "warning"
    assert [d["beaufort_class"] for d in wind["evidence"]["days"]] == [
        "strong_breeze",
        "gale_or_stronger",
    ]
    assert ind["dry_spell"]["evidence"]["longest_dry_run_days"] == 4
    assert ind["rainfall_accumulation"]["evidence"]["total_rain_mm"] == 3.5
    assert all(i["level"] == "info" for k, i in ind.items() if k in ("dry_spell",))


def test_missing_rain_day_skips_dry_spell_instead_of_guessing() -> None:
    raw = open_meteo_raw()
    raw["daily"]["precipitation_sum"] = [1.0, None, 1.0, 1.0, 1.0, 1.0, 1.0]
    got = {i["id"] for i in indicators.evaluate(normalise_open_meteo(raw))}
    assert "dry_spell" not in got and "rainfall_accumulation" not in got
    assert "heat_stress" in {n["indicator"] for n in indicators.NOT_EVALUATED}
