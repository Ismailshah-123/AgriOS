import pytest

from app.weather import indicators
from app.weather.provider import OpenMeteoProvider, ProviderError, normalise_open_meteo
from tests.weather_fixtures import open_meteo_raw


def ids(fc: dict) -> set[str]:
    return {i["id"] for i in indicators.evaluate(fc)}


def test_normalise_maps_units_and_keeps_missing_as_none() -> None:
    raw = open_meteo_raw()
    del raw["daily"]["et0_fao_evapotranspiration"]
    fc = normalise_open_meteo(raw)
    assert fc["current"]["temperature_c"] == 21.5
    assert len(fc["hourly"]) == 7 * 24 and len(fc["daily"]) == 7
    assert fc["daily"][0]["et0_fao_mm"] is None  # never invented


def test_normalise_rejects_bad_payload() -> None:
    with pytest.raises(ProviderError):
        normalise_open_meteo({"current": {}})


def test_smith_period_needs_two_consecutive_qualifying_days() -> None:
    assert "late_blight_smith_period" in ids(normalise_open_meteo(open_meteo_raw(tmin=12, rh=95)))
    assert "late_blight_smith_period" not in ids(normalise_open_meteo(open_meteo_raw(tmin=8)))
    assert "late_blight_smith_period" not in ids(normalise_open_meteo(open_meteo_raw(rh=85)))


def test_frost_indicator() -> None:
    assert "frost_risk" in ids(normalise_open_meteo(open_meteo_raw(tmin=-1)))
    assert "frost_risk" not in ids(normalise_open_meteo(open_meteo_raw(tmin=3)))


def test_rain_vs_et0_message_and_sources() -> None:
    wet = indicators.evaluate(normalise_open_meteo(open_meteo_raw(rain=6, et0=3)))
    r = next(i for i in wet if i["id"] == "rain_vs_et0")
    assert r["evidence"] == {"rain_3d_mm": 18.0, "et0_3d_mm": 9.0}
    assert "deferrable" in r["message"] and "FAO" in r["source"]
    dry = indicators.evaluate(normalise_open_meteo(open_meteo_raw(rain=0.5, et0=5)))
    assert "below" in next(i for i in dry if i["id"] == "rain_vs_et0")["message"]
    for ind in wet:
        assert ind["kind"] == "indicator" and ind["source"]


def test_rain_vs_et0_skipped_when_et0_missing() -> None:
    raw = open_meteo_raw()
    raw["daily"]["et0_fao_evapotranspiration"] = [None] * 7
    assert "rain_vs_et0" not in ids(normalise_open_meteo(raw))


def test_provider_requires_https() -> None:
    with pytest.raises(ValueError):
        OpenMeteoProvider("http://api.open-meteo.com/v1/forecast")
