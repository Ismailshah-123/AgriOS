"""Agentic layer: orchestration, cross-module report, tool permissions, approvals, isolation.
Weather comes from the synthetic FakeProvider (no network)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.agents.models import AgentAction
from app.audit.models import AuditEvent
from app.weather.router import get_weather_provider
from tests.support import API, create_cycle, create_farm, create_field, register
from tests.weather_fixtures import FakeProvider

pytestmark = pytest.mark.db
REPORT = "Give me a complete condition report for my tomato field"
SOIL = {  # clearly labelled test data
    "sampled_on": "2026-10-15",
    "data_origin": "measured",
    "lab_name": "TEST LAB (fixture)",
    "ph": "7.9",
    "ph_method": "water_1_1",
    "ec_ds_m": "3.1",
    "ec_method": "saturated_paste_ece",
}


def _farm_field(app: FastAPI, c: TestClient, email: str, located: bool = True) -> tuple:
    app.dependency_overrides[get_weather_provider] = lambda: FakeProvider()
    h = register(c, email)
    farm = create_farm(c, h)
    if located:
        c.patch(
            f"{API}/farms/{farm['id']}", headers=h, json={"latitude": "31.52", "longitude": "74.36"}
        )
    field = create_field(c, h, farm["id"])
    return h, farm, field


def _run(c: TestClient, h: dict, msg: str, **ids: str) -> dict:
    r = c.post(f"{API}/agent/runs", headers=h, json={"message": msg, **ids})
    assert r.status_code == 201, r.text
    return r.json()


def test_complete_field_report_combines_modules(db_app: FastAPI, db_client: TestClient) -> None:
    db_client = TestClient(db_app, raise_server_exceptions=True)  # DEBUG-TEMP
    h, _, field = _farm_field(db_app, db_client, "ag1@example.com")
    sow = (date.today() - timedelta(days=80)).isoformat()
    create_cycle(db_client, h, field["id"], status="active", sowing_date=sow)
    assert (
        db_client.post(
            f"{API}/soil-observations", headers=h, json={**SOIL, "field_id": field["id"]}
        ).status_code
        == 201
    )
    run = _run(db_client, h, REPORT, field_id=field["id"])
    resp, rep = run["response"], run["response"]["report"]
    assert run["intent"] == "field_report" and resp["llm_used"] is False
    assert set(run["agents"]) == {"soil", "weather", "irrigation", "crop_health"}
    assert rep["coverage"] == {
        "soil": "ok",
        "weather": "ok",
        "irrigation": "ok",
        "crop_health": "unavailable",
    }
    assert rep["crop"]["crop"] == "tomato" and rep["crop"]["fao56_stage"] == "mid_season"
    assert rep["soil"]["sampled_on"] == "2026-10-15" and rep["soil"]["data_origin"] == "measured"
    assert rep["risks"] and all(r["source"] for r in rep["risks"])
    assert rep["water_demand"]["totals"]["etc_low_mm"] > 0
    assert rep["timestamps"]["weather_retrieved_at"] and rep["timestamps"]["soil_sampled_on"]
    assert "crop_doctor_case" in resp["missing_information"]
    assert any(m.startswith("crop_doctor_model:") for m in resp["missing_information"])
    assert run["status"] == "partial"  # crop health unavailable is reported, not invented
    tools = [s["tool"] for s in run["steps"]]
    assert tools[0] == "get_field_context" and {
        "get_soil_summary",
        "get_weather",
        "get_water_demand",
        "get_crop_health",
    } <= set(tools)
    assert all(s["mode"] == "read" for s in run["steps"])
    hist = db_client.get(f"{API}/agent/runs", headers=h).json()
    assert hist["items"][0]["id"] == run["id"]


def test_partial_report_names_missing_data(db_app: FastAPI, db_client: TestClient) -> None:
    h, _, field = _farm_field(db_app, db_client, "ag2@example.com", located=False)
    run = _run(db_client, h, REPORT)  # only field: selected automatically
    rep, missing = run["response"]["report"], run["response"]["missing_information"]
    assert run["field_id"] == field["id"]
    assert rep["coverage"]["weather"] == "unavailable" and rep["coverage"]["soil"] == "unavailable"
    assert {"farm.coordinates", "weather:location_missing", "active_crop_cycle"} <= set(missing)
    assert rep["weather"]["current"] is None and rep["risks"] == []


def test_intents_and_help(db_app: FastAPI, db_client: TestClient) -> None:
    h, _, field = _farm_field(db_app, db_client, "ag3@example.com")
    assert (
        _run(db_client, h, "Will it rain this week?", field_id=field["id"])["intent"] == "weather"
    )
    assert _run(db_client, h, "موسم کیسا ہے", field_id=field["id"])["intent"] == "weather"
    assert _run(db_client, h, "What is the soil pH?", field_id=field["id"])["intent"] == "soil"
    k = _run(db_client, h, "Explain the source of the Smith period method")
    assert k["intent"] == "knowledge"
    assert any("Smith" in f for f in k["response"]["sections"][0]["findings"])
    assert _run(db_client, h, "hello")["intent"] == "help"


def test_write_needs_approval_then_executes_with_audit(
    db_app: FastAPI, db_client: TestClient, db_session: Session
) -> None:
    h, farm, field = _farm_field(db_app, db_client, "ag4@example.com", located=False)
    run = _run(db_client, h, "set farm location to 31.55, 74.34", field_id=field["id"])
    assert run["intent"] == "update_records" and len(run["actions"]) == 1
    act = run["actions"][0]
    assert act["status"] == "pending" and act["tool"] == "set_farm_location"
    assert db_client.get(f"{API}/farms/{farm['id']}", headers=h).json()["latitude"] is None
    pending = db_client.get(f"{API}/agent/actions", headers=h, params={"status": "pending"})
    assert [a["id"] for a in pending.json()] == [act["id"]]
    r = db_client.post(f"{API}/agent/actions/{act['id']}/approve", headers=h)
    assert r.status_code == 200 and r.json()["status"] == "executed", r.text
    assert r.json()["decided_by"] == r.json()["executed_by"] == r.json()["requested_by"]
    assert db_client.get(f"{API}/farms/{farm['id']}", headers=h).json()["latitude"] == 31.55
    again = db_client.post(f"{API}/agent/actions/{act['id']}/approve", headers=h)
    assert again.status_code == 409
    actions = set(
        db_session.scalars(select(AuditEvent.action).where(AuditEvent.entity_id == act["id"]))
    )
    assert {"agent_action.proposed", "agent_action.approved", "agent_action.executed"} <= actions


def test_reject_and_expiry(db_app: FastAPI, db_client: TestClient, db_session: Session) -> None:
    h, _, field = _farm_field(db_app, db_client, "ag5@example.com")
    create_cycle(db_client, h, field["id"], status="active", sowing_date="2026-10-01")
    a1 = _run(db_client, h, "set sowing date 2026-10-05", field_id=field["id"])["actions"][0]
    assert a1["tool"] == "set_cycle_sowing_date"
    r = db_client.post(f"{API}/agent/actions/{a1['id']}/reject", headers=h)
    assert r.json()["status"] == "rejected"
    a2 = _run(db_client, h, "set sowing date 2026-10-07", field_id=field["id"])["actions"][0]
    db_session.execute(
        update(AgentAction)
        .where(AgentAction.id == a2["id"])
        .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    db_session.commit()
    assert db_client.post(f"{API}/agent/actions/{a2['id']}/approve", headers=h).status_code == 409
    got = db_client.get(f"{API}/agent/actions", headers=h).json()
    assert {a["id"]: a["status"] for a in got}[a2["id"]] == "expired"


def test_tenant_isolation(db_app: FastAPI, db_client: TestClient) -> None:
    h, farm, field = _farm_field(db_app, db_client, "ag6@example.com", located=False)
    run = _run(db_client, h, "set farm location to 31.55, 74.34", field_id=field["id"])
    other = register(db_client, "ag7@example.com")
    for body in ({"field_id": field["id"]}, {"farm_id": farm["id"]}):
        r = db_client.post(f"{API}/agent/runs", headers=other, json={"message": REPORT, **body})
        assert r.status_code == 404
    assert db_client.get(f"{API}/agent/runs/{run['id']}", headers=other).status_code == 404
    aid = run["actions"][0]["id"]
    assert db_client.post(f"{API}/agent/actions/{aid}/approve", headers=other).status_code == 404
    assert db_client.get(f"{API}/agent/actions", headers=other).json() == []
    assert db_client.post(f"{API}/agent/runs", json={"message": REPORT}).status_code == 401


def test_catalogue_declares_schemas_and_write_approval(
    db_app: FastAPI, db_client: TestClient
) -> None:
    h, _, _ = _farm_field(db_app, db_client, "ag8@example.com")
    cat = db_client.get(f"{API}/agent/catalogue", headers=h).json()
    assert len(cat["agents"]) == 6 and cat["llm_used"] is False
    tools = {t["name"]: t for t in cat["tools"]}
    assert {n for n, t in tools.items() if t["mode"] == "write"} == {
        "set_farm_location",
        "set_cycle_sowing_date",
    }
    assert all(t["requires_approval"] == (t["mode"] == "write") for t in tools.values())
    assert all(t["input_schema"] and t["output_schema"] for t in tools.values())
