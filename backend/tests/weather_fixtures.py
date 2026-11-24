"""Synthetic Open-Meteo-shaped payloads for tests (clearly synthetic, never shown to users)."""

from typing import Any


def open_meteo_raw(
    days: int = 7, *, tmin: float = 12.0, rh: float = 95.0, rain: float = 2.0, et0: float = 4.0
) -> dict[str, Any]:
    dates = [f"2026-11-{23 + d:02d}" for d in range(days)]
    hours = [f"{d}T{h:02d}:00" for d in dates for h in range(24)]
    return {
        "timezone": "Asia/Karachi",
        "utc_offset_seconds": 18000,
        "current": {
            "time": "2026-11-23T10:00",
            "temperature_2m": 21.5,
            "relative_humidity_2m": 60,
            "precipitation": 0.0,
            "wind_speed_10m": 7.2,
            "weather_code": 1,
        },
        "hourly": {
            "time": hours,
            "temperature_2m": [tmin + (h % 24) / 4 for h in range(len(hours))],
            "relative_humidity_2m": [rh if (h % 24) < 12 else 70 for h in range(len(hours))],
            "precipitation": [0.1] * len(hours),
            "precipitation_probability": [40] * len(hours),
        },
        "daily": {
            "time": dates,
            "temperature_2m_max": [tmin + 6] * days,
            "temperature_2m_min": [tmin] * days,
            "precipitation_sum": [rain] * days,
            "precipitation_probability_max": [60] * days,
            "wind_speed_10m_max": [12.0] * days,
            "et0_fao_evapotranspiration": [et0] * days,
        },
    }


class FakeProvider:
    name = "fake"
    attribution = {
        "name": "Fake test provider",
        "url": "https://example.invalid",
        "licence": "test",
        "model": "synthetic",
    }

    def __init__(self, payload: dict[str, Any] | None = None, fail: bool = False) -> None:
        from app.weather.provider import normalise_open_meteo

        self.payload = normalise_open_meteo(payload or open_meteo_raw())
        self.fail = fail
        self.calls = 0

    def fetch(self, lat: float, lon: float) -> dict[str, Any]:
        from app.weather.provider import ProviderError

        self.calls += 1
        if self.fail:
            raise ProviderError("unreachable: test")
        return self.payload
