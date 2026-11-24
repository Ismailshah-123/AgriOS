import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from tests.support import API, create_cycle, create_farm, create_field, crop_id, register

pytestmark = pytest.mark.db


# ------------------------------------------------------------------------ farms


def test_farm_crud_and_audit(db_client: TestClient, db_session: Session) -> None:
    h = register(db_client, "farm@example.com")
    res = db_client.post(
        f"{API}/farms",
        headers=h,
        json={
            "name": "  Green Acres ",
            "province": "punjab",
            "district": "Okara",
            "latitude": "30.81234",
            "longitude": "73.45678",
        },
    )
    assert res.status_code == 201
    farm = res.json()
    assert farm["name"] == "Green Acres"
    assert (farm["latitude"], farm["longitude"]) == (30.81, 73.46)  # coarse location
    assert farm["location_precision"] == "0.01_degree"
    assert (farm["field_count"], farm["total_area_ha"]) == (0, 0.0)

    upd = db_client.patch(f"{API}/farms/{farm['id']}", headers=h, json={"district": "Sahiwal"})
    assert upd.status_code == 200
    assert upd.json()["district"] == "Sahiwal"
    assert db_client.delete(f"{API}/farms/{farm['id']}", headers=h).status_code == 204
    assert db_client.get(f"{API}/farms/{farm['id']}", headers=h).status_code == 404

    actions = db_session.scalars(select(AuditEvent.action).where(AuditEvent.entity == "farm"))
    assert sorted(actions) == ["farm.created", "farm.deleted", "farm.updated"]
    meta = db_session.scalar(select(AuditEvent.meta).where(AuditEvent.action == "farm.updated"))
    assert meta == {"fields": ["district"]}


def test_user_can_have_many_farms_but_names_unique_case_insensitive(
    db_client: TestClient,
) -> None:
    h = register(db_client, "many@example.com")
    create_farm(db_client, h, "Farm One")
    create_farm(db_client, h, "Farm Two")  # regression: functional index on lower(name)
    res = db_client.post(f"{API}/farms", headers=h, json={"name": "farm one"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "name_taken"


@pytest.mark.parametrize(
    "body",
    [
        {"name": ""},
        {"name": "x" * 121},
        {"name": "A", "latitude": "30.1"},
        {"name": "A", "latitude": "91", "longitude": "70"},
        {"name": "A", "province": "texas"},
        {"name": "A", "owner_id": "00000000-0000-0000-0000-000000000000"},
    ],
    ids=["empty", "too-long", "lat-only", "lat-range", "bad-province", "owner-injection"],
)
def test_farm_validation(db_client: TestClient, body: dict) -> None:
    h = register(db_client, "val@example.com")
    res = db_client.post(f"{API}/farms", headers=h, json=body)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"


def test_farm_with_fields_cannot_be_deleted(db_client: TestClient) -> None:
    h = register(db_client, "del@example.com")
    farm = create_farm(db_client, h)
    create_field(db_client, h, farm["id"])
    res = db_client.delete(f"{API}/farms/{farm['id']}", headers=h)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "farm_not_empty"


def test_farm_list_pagination_and_search(db_client: TestClient) -> None:
    h = register(db_client, "page@example.com")
    for i in range(5):
        create_farm(db_client, h, f"Farm {i}")
    create_farm(db_client, h, "Orchard")
    seen: list[str] = []
    cursor = None
    while True:
        params: dict = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        page = db_client.get(f"{API}/farms", headers=h, params=params).json()
        seen += [f["name"] for f in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break
    assert len(seen) == 6
    assert len(set(seen)) == 6
    found = db_client.get(f"{API}/farms", headers=h, params={"q": "orch"}).json()["items"]
    assert [f["name"] for f in found] == ["Orchard"]
    assert db_client.get(f"{API}/farms", headers=h, params={"limit": 101}).status_code == 422
    bad = db_client.get(f"{API}/farms", headers=h, params={"cursor": "garbage!"})
    assert bad.status_code == 422


# ----------------------------------------------------------------------- fields


def test_field_area_stored_in_hectares_and_echoed(db_client: TestClient) -> None:
    h = register(db_client, "field@example.com")
    farm = create_farm(db_client, h)
    field = create_field(db_client, h, farm["id"], value="2.5", unit="acre")
    assert field["area"] == {
        "hectares": 1.0117,
        "value": 2.5,
        "unit": "acre",
        "data_origin": "farmer_entered",
    }
    assert field["farm_name"] == "Home Farm"
    farm_after = db_client.get(f"{API}/farms/{farm['id']}", headers=h).json()
    assert (farm_after["field_count"], farm_after["total_area_ha"]) == (1, 1.0117)
    upd = db_client.patch(
        f"{API}/fields/{field['id']}",
        headers=h,
        json={"area": {"value": "3", "unit": "ha"}, "area_origin": "measured"},
    )
    assert upd.json()["area"] == {
        "hectares": 3.0,
        "value": 3.0,
        "unit": "ha",
        "data_origin": "measured",
    }


@pytest.mark.parametrize(
    "area",
    [
        {"value": "0", "unit": "ha"},
        {"value": "-1", "unit": "ha"},
        {"value": "1", "unit": "kanal"},
        {"value": "1.00001", "unit": "ha"},
        {"value": "300000", "unit": "ha"},
    ],
    ids=["zero", "negative", "unverified-unit", "too-precise", "too-large"],
)
def test_field_area_validation(db_client: TestClient, area: dict) -> None:
    h = register(db_client, "area@example.com")
    farm = create_farm(db_client, h)
    res = db_client.post(
        f"{API}/fields", headers=h, json={"farm_id": farm["id"], "name": "F", "area": area}
    )
    assert res.status_code == 422


def test_field_names_unique_per_farm_and_filter_by_farm(db_client: TestClient) -> None:
    h = register(db_client, "ff@example.com")
    a, b = create_farm(db_client, h, "A"), create_farm(db_client, h, "B")
    create_field(db_client, h, a["id"], "Plot 1")
    create_field(db_client, h, b["id"], "Plot 1")  # same name on another farm is fine
    dup = db_client.post(
        f"{API}/fields",
        headers=h,
        json={"farm_id": a["id"], "name": "PLOT 1", "area": {"value": "1", "unit": "ha"}},
    )
    assert dup.status_code == 409
    only_a = db_client.get(f"{API}/fields", headers=h, params={"farm_id": a["id"]}).json()
    assert [f["farm_name"] for f in only_a["items"]] == ["A"]


# ------------------------------------------------------------------ crops/cycles


def test_crop_registry_lists_reference_crops(db_client: TestClient) -> None:
    h = register(db_client, "crops@example.com")
    crops = db_client.get(f"{API}/crops", headers=h).json()
    assert {c["code"] for c in crops} >= {"tomato", "wheat", "cotton", "rice", "maize"}
    assert all(set(c) == {"id", "code", "name_en", "name_ur", "scientific_name"} for c in crops)


def test_crop_cycle_lifecycle(db_client: TestClient) -> None:
    h = register(db_client, "cyc@example.com")
    field = create_field(db_client, h, create_farm(db_client, h)["id"])
    cycle = create_cycle(db_client, h, field["id"], variety="Local", season="rabi")
    assert cycle["status"] == "planned"
    assert cycle["crop"]["code"] == "tomato"
    assert (cycle["field_name"], cycle["farm_name"]) == ("North Field", "Home Farm")
    url = f"{API}/crop-cycles/{cycle['id']}"
    bad = db_client.patch(url, headers=h, json={"status": "active"})
    assert bad.status_code == 422
    assert bad.json()["error"]["field"] == "sowing_date"
    ok = db_client.patch(url, headers=h, json={"status": "active", "sowing_date": "2026-10-01"})
    assert ok.status_code == 200
    assert ok.json()["status"] == "active"
    field_now = db_client.get(f"{API}/fields/{field['id']}", headers=h).json()
    assert field_now["active_cycle_count"] == 1
    active = db_client.get(f"{API}/crop-cycles", headers=h, params={"status": "active"}).json()
    assert [c["id"] for c in active["items"]] == [cycle["id"]]
    res = db_client.delete(f"{API}/fields/{field['id']}", headers=h)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "field_not_empty"
    assert db_client.delete(url, headers=h).status_code == 204


def test_cycle_rejects_unknown_crop_and_oversized_area(db_client: TestClient) -> None:
    h = register(db_client, "cyc2@example.com")
    field = create_field(db_client, h, create_farm(db_client, h)["id"], value="1", unit="ha")
    res = db_client.post(
        f"{API}/crop-cycles",
        headers=h,
        json={"field_id": field["id"], "crop_id": "00000000-0000-0000-0000-000000000001"},
    )
    assert res.status_code == 404
    assert res.json()["error"]["field"] == "crop_id"
    res = db_client.post(
        f"{API}/crop-cycles",
        headers=h,
        json={"field_id": field["id"], "crop_id": crop_id(db_client, h), "area_ha": "1.5"},
    )
    assert res.status_code == 422
    assert res.json()["error"]["field"] == "area_ha"


def test_update_rules_rename_conflicts_and_coordinate_pairs(db_client: TestClient) -> None:
    h = register(db_client, "upd@example.com")
    a = create_farm(db_client, h, "Alpha")
    create_farm(db_client, h, "Beta")
    res = db_client.patch(f"{API}/farms/{a['id']}", headers=h, json={"name": "BETA"})
    assert res.status_code == 409
    located = db_client.patch(
        f"{API}/farms/{a['id']}", headers=h, json={"latitude": "31.5", "longitude": "74.3"}
    )
    assert located.status_code == 200
    half = db_client.patch(f"{API}/farms/{a['id']}", headers=h, json={"latitude": None})
    assert half.status_code == 422
    assert half.json()["error"]["field"] == "latitude"
    cleared = db_client.patch(
        f"{API}/farms/{a['id']}", headers=h, json={"latitude": None, "longitude": None}
    )
    assert cleared.json()["latitude"] is None
    f1 = create_field(db_client, h, a["id"], "One")
    create_field(db_client, h, a["id"], "Two")
    res = db_client.patch(f"{API}/fields/{f1['id']}", headers=h, json={"name": "two"})
    assert res.status_code == 409
