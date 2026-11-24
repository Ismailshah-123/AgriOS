from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.support import API, create_cycle, create_farm, create_field, crop_id, register

pytestmark = pytest.mark.db

TODAY = date.today()


def iso(days: int) -> str:
    return (TODAY + timedelta(days=days)).isoformat()


def test_new_account_overview_is_all_zero(db_client: TestClient) -> None:
    h = register(db_client, "new@example.com")
    body = db_client.get(f"{API}/overview", headers=h).json()
    assert body["counts"] == {
        "farms": 0,
        "fields": 0,
        "total_area_ha": 0.0,
        "cycles_by_status": {"planned": 0, "active": 0, "harvested": 0, "abandoned": 0},
    }
    assert body["active_cycles"] == body["upcoming"] == body["recent_changes"] == []
    intel = body["intelligence"]
    assert intel["crop_health"] == {
        "cases": 0, "awaiting_analysis": 0, "needs_follow_up": 0,
        "model_availability": "not_registered",
    }  # fmt: skip
    assert intel["soil"] == {"observations": 0, "fields_with_tests": 0, "latest_sampled_on": None}
    assert intel["weather"] == {"farms": 0, "farms_with_location": 0}
    assert intel["irrigation"] == {"growing_cycles": 0, "cycles_with_estimate": 0}
    assert intel["agents"] == {"runs": 0, "pending_approvals": 0}


def test_intelligence_summary_counts_only_own_records(db_client: TestClient) -> None:
    h = register(db_client, "intel@example.com")
    located = db_client.post(
        f"{API}/farms", headers=h, json={"name": "Located", "latitude": 31.52, "longitude": 74.35}
    ).json()
    create_farm(db_client, h, "No location")
    field = create_field(db_client, h, located["id"], value="1", unit="ha")
    create_cycle(db_client, h, field["id"], status="active", sowing_date=iso(-20))  # tomato
    db_client.post(f"{API}/crop-cycles", headers=h, json={
        "field_id": field["id"], "crop_id": crop_id(db_client, h, "rice"),
        "status": "active", "sowing_date": iso(-10),
    }).raise_for_status()  # fmt: skip  # rice: no cited Kc table -> no ETc estimate
    soil = {"sampled_on": "2026-10-01", "data_origin": "farmer_entered", "ph": "7.9",
            "ph_method": "water_1_2_5", "field_id": field["id"]}  # fmt: skip
    assert db_client.post(f"{API}/soil-observations", headers=h, json=soil).status_code == 201

    other = register(db_client, "intel-other@example.com")  # must not see any of the above
    other_intel = db_client.get(f"{API}/overview", headers=other).json()["intelligence"]
    assert other_intel["soil"]["observations"] == other_intel["weather"]["farms"] == 0

    intel = db_client.get(f"{API}/overview", headers=h).json()["intelligence"]
    assert intel["weather"] == {"farms": 2, "farms_with_location": 1}
    assert intel["irrigation"] == {"growing_cycles": 2, "cycles_with_estimate": 1}
    assert intel["soil"] == {
        "observations": 1, "fields_with_tests": 1, "latest_sampled_on": "2026-10-01",
    }  # fmt: skip


def test_overview_counts_active_cycles_and_upcoming_dates(db_client: TestClient) -> None:
    h = register(db_client, "ov@example.com")
    farm = create_farm(db_client, h)
    field = create_field(db_client, h, farm["id"], value="2", unit="ha")
    growing = create_cycle(
        db_client, h, field["id"], status="active", sowing_date=iso(-30),
        expected_harvest_date=iso(20),
    )  # fmt: skip
    planned = create_cycle(db_client, h, field["id"], sowing_date=iso(10))
    create_cycle(db_client, h, field["id"], sowing_date=iso(200))  # beyond 60-day window
    create_cycle(
        db_client, h, field["id"], status="active", sowing_date=iso(-100),
        expected_harvest_date=iso(-5),
    )  # fmt: skip  # expected harvest already passed: not "upcoming"

    body = db_client.get(f"{API}/overview", headers=h).json()
    counts = body["counts"]
    assert (counts["farms"], counts["fields"], counts["total_area_ha"]) == (1, 1, 2.0)
    assert counts["cycles_by_status"] == {"planned": 2, "active": 2, "harvested": 0, "abandoned": 0}
    assert {c["id"] for c in body["active_cycles"]} >= {growing["id"]}
    assert [(u["kind"], u["cycle"]["id"]) for u in body["upcoming"]] == [
        ("planned_sowing", planned["id"]),
        ("expected_harvest", growing["id"]),
    ]
    assert all(u["source"] == "farmer_entered" for u in body["upcoming"])


def test_recent_changes_name_live_records_and_hide_deleted_names(db_client: TestClient) -> None:
    h = register(db_client, "rc@example.com")
    keep = create_farm(db_client, h, "Kept Farm")
    gone = create_farm(db_client, h, "Gone Farm")
    db_client.delete(f"{API}/farms/{gone['id']}", headers=h)
    changes = db_client.get(f"{API}/overview", headers=h).json()["recent_changes"]
    assert [c["action"] for c in changes] == ["farm.deleted", "farm.created", "farm.created"]
    by_id = {(c["entity_id"], c["action"]): c["name"] for c in changes}
    assert by_id[(keep["id"], "farm.created")] == "Kept Farm"
    assert by_id[(gone["id"], "farm.deleted")] is None
    # Login and profile events are not farm-domain changes.
    assert all(c["entity"] in {"farm", "field", "crop_cycle"} for c in changes)


def test_overview_never_includes_other_users_data(db_client: TestClient) -> None:
    alice = register(db_client, "a-ov@example.com")
    farm = create_farm(db_client, alice)
    field = create_field(db_client, alice, farm["id"])
    create_cycle(db_client, alice, field["id"], sowing_date=iso(5))
    bob = register(db_client, "b-ov@example.com")
    body = db_client.get(f"{API}/overview", headers=bob).json()
    assert body["counts"]["farms"] == 0
    assert body["upcoming"] == body["recent_changes"] == body["active_cycles"] == []


def test_overview_requires_authentication(db_client: TestClient) -> None:
    assert db_client.get(f"{API}/overview").status_code == 401
