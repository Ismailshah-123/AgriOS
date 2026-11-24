"""FR10 economics API: owner-scoped CRUD, audited writes, PKR decimal strings, summary."""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from tests.support import API, create_cycle, create_farm, create_field, register

pytestmark = pytest.mark.db


def _cycle(client: TestClient, email: str) -> tuple[dict[str, str], str]:
    h = register(client, email)
    field = create_field(client, h, create_farm(client, h)["id"], value="2", unit="ha")
    cycle = create_cycle(client, h, field["id"], status="active", sowing_date="2026-09-01")
    return h, cycle["id"]


def test_records_and_summary_reconcile_with_hand_calculation(db_client: TestClient) -> None:
    h, cid = _cycle(db_client, "econ@example.com")
    for cat, amt in [
        ("seed", "12500.00"),
        ("fertilizer", "18750.50"),
        ("labour", "9000"),
        ("fertilizer", "1249.50"),
    ]:
        r = db_client.post(
            f"{API}/expenses",
            headers=h,
            json={
                "crop_cycle_id": cid,
                "category": cat,
                "amount_pkr": amt,
                "incurred_on": "2026-10-01",
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["currency"] == "PKR" and r.json()["data_origin"] == "farmer_entered"
    for qty, price in [("2000", "30.00"), ("500", "25.50"), ("300", None)]:
        r = db_client.post(
            f"{API}/harvest-sales",
            headers=h,
            json={
                "crop_cycle_id": cid,
                "recorded_on": "2026-11-01",
                "quantity_kg": qty,
                "price_pkr_per_kg": price,
            },
        )
        assert r.status_code == 201, r.text
    body = db_client.get(f"{API}/crop-cycles/{cid}/economics", headers=h).json()
    s = body["summary"]
    assert body["currency"] == "PKR" and len(body["expenses"]) == 4 and len(body["harvests"]) == 3
    assert (s["total_cost_pkr"], s["revenue_pkr"], s["profit_pkr"]) == (
        "41500.00",
        "72750.00",
        "31250.00",
    )
    assert (s["cost_per_ha_pkr"], s["cost_per_acre_pkr"]) == ("20750.00", "8397.23")
    assert (s["break_even_price_pkr_per_kg"], s["break_even_yield_kg"]) == ("14.82", "1426.12")
    assert {h_["revenue_pkr"] for h_ in body["harvests"]} == {"60000.00", "12750.00", None}
    assert body["definitions"] and body["limitations"]


def test_update_delete_validation_and_audit(db_client: TestClient, db_session: Session) -> None:
    h, cid = _cycle(db_client, "econ2@example.com")
    e = db_client.post(
        f"{API}/expenses",
        headers=h,
        json={
            "crop_cycle_id": cid,
            "category": "seed",
            "amount_pkr": "100.00",
            "incurred_on": "2026-10-01",
        },
    ).json()
    r = db_client.patch(f"{API}/expenses/{e['id']}", headers=h, json={"amount_pkr": "150.25"})
    assert r.status_code == 200 and r.json()["amount_pkr"] == "150.25"
    assert (
        db_client.patch(
            f"{API}/expenses/{e['id']}", headers=h, json={"amount_pkr": None}
        ).status_code
        == 422
    )
    future = (date.today() + timedelta(days=2)).isoformat()
    bad = [
        {"amount_pkr": "0"},
        {"amount_pkr": "1.234"},
        {"incurred_on": future},
        {"category": "bribes"},
    ]
    for b in bad:
        body = {
            "crop_cycle_id": cid,
            "category": "seed",
            "amount_pkr": "1",
            "incurred_on": "2026-10-01",
            **b,
        }
        assert db_client.post(f"{API}/expenses", headers=h, json=body).status_code == 422, b
    hs = db_client.post(
        f"{API}/harvest-sales",
        headers=h,
        json={"crop_cycle_id": cid, "recorded_on": "2026-11-01", "quantity_kg": "10"},
    ).json()
    r = db_client.patch(
        f"{API}/harvest-sales/{hs['id']}", headers=h, json={"price_pkr_per_kg": "40"}
    )
    assert r.json()["revenue_pkr"] == "400.00"
    assert db_client.delete(f"{API}/expenses/{e['id']}", headers=h).status_code == 204
    actions = set(
        db_session.scalars(
            select(AuditEvent.action).where(AuditEvent.entity.in_(["expense", "harvest_sale"]))
        )
    )
    assert actions == {
        "expense.created",
        "expense.updated",
        "expense.deleted",
        "harvest_sale.created",
        "harvest_sale.updated",
    }


def test_other_users_get_404_and_cannot_attach_records(db_client: TestClient) -> None:
    h, cid = _cycle(db_client, "econ3@example.com")
    e = db_client.post(
        f"{API}/expenses",
        headers=h,
        json={
            "crop_cycle_id": cid,
            "category": "seed",
            "amount_pkr": "5",
            "incurred_on": "2026-10-01",
        },
    ).json()
    other = register(db_client, "econ-other@example.com")
    assert db_client.get(f"{API}/crop-cycles/{cid}/economics", headers=other).status_code == 404
    assert (
        db_client.patch(f"{API}/expenses/{e['id']}", headers=other, json={"note": "x"}).status_code
        == 404
    )
    assert db_client.delete(f"{API}/expenses/{e['id']}", headers=other).status_code == 404
    r = db_client.post(
        f"{API}/harvest-sales",
        headers=other,
        json={"crop_cycle_id": cid, "recorded_on": "2026-11-01", "quantity_kg": "1"},
    )
    assert r.status_code == 404


def test_cycle_with_records_cannot_be_deleted_409_not_500(db_client: TestClient) -> None:
    h, cid = _cycle(db_client, "econ4@example.com")
    db_client.post(
        f"{API}/expenses",
        headers=h,
        json={
            "crop_cycle_id": cid,
            "category": "seed",
            "amount_pkr": "5",
            "incurred_on": "2026-10-01",
        },
    )
    r = db_client.delete(f"{API}/crop-cycles/{cid}", headers=h)
    assert r.status_code == 409 and r.json()["error"]["code"] == "cycle_not_empty"
    assert db_client.get(f"{API}/crop-cycles/{cid}/economics", headers=h).status_code == 200
