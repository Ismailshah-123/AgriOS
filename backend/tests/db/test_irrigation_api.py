from datetime import date, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.weather.router import get_weather_provider
from tests.support import API, create_cycle, create_farm, create_field, register
from tests.weather_fixtures import FakeProvider

pytestmark = pytest.mark.db


def _setup(app: FastAPI, client: TestClient, email: str, located: bool = True) -> tuple:
    app.dependency_overrides[get_weather_provider] = lambda: FakeProvider()
    h = register(client, email)
    farm = create_farm(client, h)
    if located:
        r = client.patch(
            f"{API}/farms/{farm['id']}", headers=h, json={"latitude": "31.52", "longitude": "74.36"}
        )
        assert r.status_code == 200
    field = create_field(client, h, farm["id"])
    return h, field


def test_water_demand_reports_missing_cycle_then_computes_etc(
    db_app: FastAPI, db_client: TestClient
) -> None:
    h, field = _setup(db_app, db_client, "irr1@example.com")
    url = f"{API}/fields/{field['id']}/water-demand"
    body = db_client.get(url, headers=h).json()
    assert body["status"] == "unavailable" and body["missing_information"] == ["active_crop_cycle"]
    sow = (date.today() - timedelta(days=80)).isoformat()  # tomato mid-season (70-110)
    create_cycle(db_client, h, field["id"], status="active", sowing_date=sow)
    body = db_client.get(url, headers=h).json()
    assert body["status"] == "ok", body
    assert body["data_origin"] == "inferred" and body["soil_moisture"] == "not_measured"
    assert body["effective_rainfall"] == "not_applied"
    day = next(d for d in body["daily"] if d["etc_low_mm"] is not None)
    assert day["etc_low_mm"] == round(day["kc_low"] * day["et0_mm"], 2)
    assert body["totals"]["et0_mm"] > 0 and body["units"]["etc"] == "mm/day"


def test_water_demand_needs_coordinates_and_is_owner_only(
    db_app: FastAPI, db_client: TestClient
) -> None:
    h, field = _setup(db_app, db_client, "irr2@example.com", located=False)
    create_cycle(db_client, h, field["id"], status="active", sowing_date="2026-10-01")
    body = db_client.get(f"{API}/fields/{field['id']}/water-demand", headers=h).json()
    assert "weather:location_missing" in body["missing_information"]
    assert body["status"] == "unavailable" and body["totals"] is None
    other = register(db_client, "irr3@example.com")
    r = db_client.get(f"{API}/fields/{field['id']}/water-demand", headers=other)
    assert r.status_code == 404
