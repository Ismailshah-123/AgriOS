import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from tests.support import API, create_cycle, create_farm, create_field, register

pytestmark = pytest.mark.db

LAB = {
    "sampled_on": "2026-10-01",
    "data_origin": "measured",
    "lab_name": "District Soil Testing Lab",
    "ph": "8.6",
    "ph_method": "water_1_2_5",
    "ec_ds_m": "4.5",
    "ec_method": "saturated_paste_ece",
    "organic_matter_pct": "0.75",
    "phosphorus_mg_kg": "6.2",
    "phosphorus_method": "olsen",
    "potassium_mg_kg": "110",
    "texture": "silt_loam",
}


def _field(client: TestClient, h: dict[str, str]) -> dict:
    farm = create_farm(client, h)
    return create_field(client, h, farm["id"])


def test_create_interpret_history_and_audit(db_client: TestClient, db_session: Session) -> None:
    h = register(db_client, "s1@example.com")
    field = _field(db_client, h)
    create_cycle(db_client, h, field["id"], status="planned")
    r = db_client.post(f"{API}/soil-observations", headers=h, json={**LAB, "field_id": field["id"]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["ph"] == 8.6 and body["units"]["ec_ds_m"] == "dS/m"
    assert body["crops_considered"] == ["tomato"]
    classes = {f["class"] for f in body["interpretation"]["flags"]}
    assert {
        "strongly_alkaline",
        "possible_sodicity",
        "slightly_saline",
        "above_crop_threshold",
    } <= classes
    assert all(f["source"] for f in body["interpretation"]["flags"])
    older = {
        **LAB,
        "field_id": field["id"],
        "sampled_on": "2025-10-01",
        "ph": "8.1",
        "ec_ds_m": "3.0",
    }
    assert db_client.post(f"{API}/soil-observations", headers=h, json=older).status_code == 201
    hist = db_client.get(
        f"{API}/soil-observations", headers=h, params={"field_id": field["id"]}
    ).json()
    assert [o["sampled_on"] for o in hist] == ["2026-10-01", "2025-10-01"]
    s = db_client.get(f"{API}/fields/{field['id']}/soil-summary", headers=h).json()
    assert s["observations"] == 2 and s["latest"]["sampled_on"] == "2026-10-01"
    assert [p["value"] for p in s["trends"]["ph"]] == [8.1, 8.6]
    actions = db_session.scalars(
        select(AuditEvent.action).where(AuditEvent.entity == "soil_observation")
    ).all()
    assert actions.count("soil_observation.created") == 2


def test_validation_rules(db_client: TestClient) -> None:
    h = register(db_client, "s2@example.com")
    fid = _field(db_client, h)["id"]

    def post(**kw: object) -> int:
        return db_client.post(
            f"{API}/soil-observations", headers=h, json={**LAB, "field_id": fid, **kw}
        ).status_code

    assert post(ph="14.5") == 422
    assert post(ec_ds_m="-1") == 422
    assert post(sampled_on="2999-01-01") == 422
    assert post(lab_name=None) == 422  # measured needs a lab
    assert post(lab_name=None, data_origin="farmer_entered") == 201
    assert post(data_origin="simulated") == 422  # simulated soil values are never accepted
    empty = {
        k: None
        for k in (
            "ph",
            "ec_ds_m",
            "organic_matter_pct",
            "phosphorus_mg_kg",
            "potassium_mg_kg",
            "texture",
        )
    }
    assert post(**empty) == 422
    assert post(depth_from_cm="30", depth_to_cm="15") == 422


def test_update_delete_and_ownership(db_client: TestClient, db_session: Session) -> None:
    h = register(db_client, "s3@example.com")
    fid = _field(db_client, h)["id"]
    oid = db_client.post(
        f"{API}/soil-observations", headers=h, json={**LAB, "field_id": fid}
    ).json()["id"]
    other = register(db_client, "s4@example.com")
    assert db_client.get(f"{API}/soil-observations/{oid}", headers=other).status_code == 404
    assert (
        db_client.patch(
            f"{API}/soil-observations/{oid}", headers=other, json={"ph": "7"}
        ).status_code
        == 404
    )
    assert db_client.delete(f"{API}/soil-observations/{oid}", headers=other).status_code == 404
    assert (
        db_client.get(
            f"{API}/soil-observations", headers=other, params={"field_id": fid}
        ).status_code
        == 404
    )
    assert db_client.get(f"{API}/fields/{fid}/soil-summary", headers=other).status_code == 404
    bad = {**LAB, "field_id": fid}
    assert db_client.post(f"{API}/soil-observations", headers=other, json=bad).status_code == 404
    up = db_client.patch(f"{API}/soil-observations/{oid}", headers=h, json={"ph": "7.0"})
    assert up.status_code == 200 and up.json()["ph"] == 7.0
    assert (
        db_client.patch(
            f"{API}/soil-observations/{oid}",
            headers=h,
            json={"depth_from_cm": "50", "depth_to_cm": "10"},
        ).status_code
        == 422
    )
    assert db_client.delete(f"{API}/soil-observations/{oid}", headers=h).status_code == 204
    assert db_client.get(f"{API}/soil-observations/{oid}", headers=h).status_code == 404
    acts = set(
        db_session.scalars(select(AuditEvent.action).where(AuditEvent.entity_id.is_not(None))).all()
    )
    assert {"soil_observation.updated", "soil_observation.deleted"} <= acts


def test_secondary_and_micronutrients_stored_with_units_never_interpreted(
    db_client: TestClient,
) -> None:
    h = register(db_client, "soil-micro@example.com")
    fid = _field(db_client, h)["id"]
    body = {
        **LAB,
        "field_id": fid,
        "zinc_mg_kg": "0.62",
        "boron_mg_kg": "0.4",
        "cec_cmol_kg": "12.5",
        "calcium_mg_kg": "1800",
        "nutrient_methods": {"zinc_mg_kg": "DTPA (test fixture)", "boron_mg_kg": "hot water"},
    }
    r = db_client.post(f"{API}/soil-observations", headers=h, json=body)
    assert r.status_code == 201, r.text
    out = r.json()
    assert out["zinc_mg_kg"] == 0.62 and out["cec_cmol_kg"] == 12.5
    assert out["sulfur_mg_kg"] is None  # not reported stays None, never 0
    assert out["units"]["cec_cmol_kg"] == "cmol(+)/kg"
    assert out["nutrient_methods"]["zinc_mg_kg"] == "DTPA (test fixture)"
    not_eval = {n["measure"] for n in out["interpretation"]["not_evaluated"]}
    assert {"zinc_mg_kg", "boron_mg_kg", "cec_cmol_kg", "calcium_mg_kg"} <= not_eval
    assert not any(f["measure"] == "zinc_mg_kg" for f in out["interpretation"]["flags"])
    bad = {**body, "nutrient_methods": {"ph": "x"}}
    assert db_client.post(f"{API}/soil-observations", headers=h, json=bad).status_code == 422
