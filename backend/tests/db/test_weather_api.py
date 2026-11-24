from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.weather.models import WeatherSnapshot
from app.weather.router import get_weather_provider
from tests.support import API, create_farm, create_field, register
from tests.weather_fixtures import FakeProvider

pytestmark = pytest.mark.db


def _located_farm(client: TestClient, h: dict[str, str]) -> dict:
    farm = create_farm(client, h)
    res = client.patch(
        f"{API}/farms/{farm['id']}", headers=h, json={"latitude": "31.52", "longitude": "74.36"}
    )
    assert res.status_code == 200
    return res.json()


def _use(app: FastAPI, provider: FakeProvider | None) -> None:
    app.dependency_overrides[get_weather_provider] = lambda: provider


def test_field_weather_fresh_then_cached(db_app: FastAPI, db_client: TestClient) -> None:
    fake = FakeProvider()
    _use(db_app, fake)
    h = register(db_client, "w1@example.com")
    farm = _located_farm(db_client, h)
    field = create_field(db_client, h, farm["id"])
    r = db_client.get(f"{API}/weather", headers=h, params={"field_id": field["id"]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "fresh" and body["data_origin"] == "retrieved"
    assert body["location"]["field_id"] == field["id"]
    assert body["current"]["temperature_c"] == 21.5 and body["units"]["temperature"] == "°C"
    assert len(body["daily"]) == 7 and 0 < len(body["hourly"]) <= 72
    assert body["provider"]["name"] == "Fake test provider"
    assert {i["id"] for i in body["indicators"]} >= {"late_blight_smith_period", "rain_vs_et0"}
    r2 = db_client.get(f"{API}/weather", headers=h, params={"farm_id": farm["id"]})
    assert r2.json()["status"] == "fresh" and fake.calls == 1  # served from cache


def test_stale_cache_when_provider_fails(
    db_app: FastAPI, db_client: TestClient, db_session: Session
) -> None:
    _use(db_app, FakeProvider())
    h = register(db_client, "w2@example.com")
    farm = _located_farm(db_client, h)
    assert (
        db_client.get(f"{API}/weather", headers=h, params={"farm_id": farm["id"]}).status_code
        == 200
    )
    db_session.execute(
        update(WeatherSnapshot).values(fetched_at=datetime.now(UTC) - timedelta(hours=2))
    )
    _use(db_app, FakeProvider(fail=True))
    body = db_client.get(f"{API}/weather", headers=h, params={"farm_id": farm["id"]}).json()
    assert body["status"] == "stale" and body["reason"] == "provider_error"
    assert body["age_minutes"] >= 119
    db_session.execute(
        update(WeatherSnapshot).values(fetched_at=datetime.now(UTC) - timedelta(hours=30))
    )
    body = db_client.get(f"{API}/weather", headers=h, params={"farm_id": farm["id"]}).json()
    assert body["status"] == "unavailable" and body["current"] is None


def test_unavailable_states_never_fake_readings(db_app: FastAPI, db_client: TestClient) -> None:
    h = register(db_client, "w3@example.com")
    farm = create_farm(db_client, h)  # no location
    _use(db_app, FakeProvider())
    body = db_client.get(f"{API}/weather", headers=h, params={"farm_id": farm["id"]}).json()
    assert body["status"] == "unavailable" and body["reason"] == "location_missing"
    assert body["current"] is None and body["daily"] == []
    _use(db_app, None)  # WEATHER_PROVIDER=disabled
    h2 = register(db_client, "w5@example.com")
    loc = _located_farm(db_client, h2)
    body = db_client.get(f"{API}/weather", headers=h2, params={"farm_id": loc["id"]}).json()
    assert body["status"] == "unavailable" and body["reason"] == "provider_disabled"


def test_ownership_and_validation(
    db_app: FastAPI, db_client: TestClient, db_session: Session
) -> None:
    _use(db_app, FakeProvider())
    owner = register(db_client, "w6@example.com")
    farm = _located_farm(db_client, owner)
    other = register(db_client, "w7@example.com")
    assert (
        db_client.get(f"{API}/weather", headers=other, params={"farm_id": farm["id"]}).status_code
        == 404
    )
    assert db_client.get(f"{API}/weather", headers=owner).status_code == 422
    assert db_client.get(f"{API}/weather", params={"farm_id": farm["id"]}).status_code == 401
    assert db_session.scalar(select(WeatherSnapshot)) is None  # nothing fetched for others
