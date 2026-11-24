"""Weather provider abstraction + Open-Meteo implementation (stdlib HTTP, no API key).

A provider returns a normalised `Forecast` dict or raises `ProviderError`. It never
returns invented values: missing fields stay None.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Protocol

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
OPEN_METEO_ATTRIBUTION = {
    "name": "Open-Meteo",
    "url": "https://open-meteo.com/",
    "licence": "CC BY 4.0 (weather data); free API tier is for non-commercial use",
    "model": "Open-Meteo best-match numerical weather prediction blend",
}

_CURRENT = "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,weather_code"
_HOURLY = "temperature_2m,relative_humidity_2m,precipitation,precipitation_probability"
_DAILY = (
    "temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,"
    "wind_speed_10m_max,et0_fao_evapotranspiration"
)


class ProviderError(RuntimeError):
    """Provider unreachable, timed out, or returned an unusable payload."""


class WeatherProvider(Protocol):
    name: str
    attribution: dict[str, str]

    def fetch(self, lat: float, lon: float) -> dict[str, Any]: ...


def _col(block: dict[str, Any], key: str, n: int) -> list[Any]:
    v = block.get(key)
    return list(v) if isinstance(v, list) and len(v) == n else [None] * n


def normalise_open_meteo(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        cur = raw["current"]
        hourly, daily = raw["hourly"], raw["daily"]
        ht, dt = list(hourly["time"]), list(daily["time"])
    except (KeyError, TypeError) as e:
        raise ProviderError(f"unexpected payload: missing {e}") from e
    hcols = {k: _col(hourly, k, len(ht)) for k in _HOURLY.split(",")}
    dcols = {k: _col(daily, k, len(dt)) for k in _DAILY.split(",")}
    return {
        "timezone": raw.get("timezone"),
        "utc_offset_seconds": raw.get("utc_offset_seconds"),
        "current": {
            "time": cur.get("time"),
            "temperature_c": cur.get("temperature_2m"),
            "relative_humidity_pct": cur.get("relative_humidity_2m"),
            "precipitation_mm": cur.get("precipitation"),
            "wind_speed_kmh": cur.get("wind_speed_10m"),
            "weather_code": cur.get("weather_code"),
        },
        "hourly": [
            {
                "time": t,
                "temperature_c": hcols["temperature_2m"][i],
                "relative_humidity_pct": hcols["relative_humidity_2m"][i],
                "precipitation_mm": hcols["precipitation"][i],
                "precipitation_probability_pct": hcols["precipitation_probability"][i],
            }
            for i, t in enumerate(ht)
        ],
        "daily": [
            {
                "date": d,
                "temperature_max_c": dcols["temperature_2m_max"][i],
                "temperature_min_c": dcols["temperature_2m_min"][i],
                "precipitation_sum_mm": dcols["precipitation_sum"][i],
                "precipitation_probability_max_pct": dcols["precipitation_probability_max"][i],
                "wind_speed_max_kmh": dcols["wind_speed_10m_max"][i],
                "et0_fao_mm": dcols["et0_fao_evapotranspiration"][i],
            }
            for i, d in enumerate(dt)
        ],
    }


class OpenMeteoProvider:
    name = "open_meteo"
    attribution = OPEN_METEO_ATTRIBUTION

    def __init__(self, base_url: str = OPEN_METEO_URL, timeout_s: float = 8.0) -> None:
        if not base_url.startswith("https://"):
            raise ValueError("weather provider URL must be https")
        self.base_url = base_url
        self.timeout_s = timeout_s

    def fetch(self, lat: float, lon: float) -> dict[str, Any]:
        q = urllib.parse.urlencode(
            {
                "latitude": f"{lat:.2f}",
                "longitude": f"{lon:.2f}",
                "current": _CURRENT,
                "hourly": _HOURLY,
                "daily": _DAILY,
                "timezone": "auto",
                "forecast_days": 7,
                "wind_speed_unit": "kmh",
            }
        )
        req = urllib.request.Request(  # noqa: S310 - fixed https base URL validated above
            f"{self.base_url}?{q}", headers={"User-Agent": "AgriOS/0.1 (weather module)"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:  # noqa: S310
                if resp.status != 200:
                    raise ProviderError(f"HTTP {resp.status}")
                body = resp.read(2_000_000)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ProviderError(f"unreachable: {type(e).__name__}") from e
        try:
            raw = json.loads(body)
        except ValueError as e:
            raise ProviderError("invalid JSON") from e
        if raw.get("error"):
            raise ProviderError(str(raw.get("reason", "provider error"))[:200])
        return normalise_open_meteo(raw)
