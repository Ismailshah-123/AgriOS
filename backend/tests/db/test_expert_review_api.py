"""FR12 expert review: request, role-gated queue, visibility, outcome, audit, status rules."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.identity.models import User, UserRole
from tests.images import make_image
from tests.support import API, create_cycle, create_farm, create_field, register

pytestmark = pytest.mark.db


def _case(client: TestClient, email: str) -> tuple[dict[str, str], str]:
    h = register(client, email)
    field = create_field(client, h, create_farm(client, h)["id"])
    cycle = create_cycle(client, h, field["id"], status="active", sowing_date="2026-10-01")
    r = client.post(
        f"{API}/cases",
        headers=h,
        data={"crop_cycle_id": cycle["id"]},
        files=[("images", ("a.jpg", make_image(), "image/jpeg"))],
    )
    assert r.status_code == 201, r.text
    return h, r.json()["id"]


def _expert(client: TestClient, db: Session, email: str) -> dict[str, str]:
    h = register(client, email, name="Dr Agronomist")
    db.execute(update(User).where(User.email == email).values(role=UserRole.EXPERT))
    db.flush()
    return h


def test_full_review_flow_with_visibility_and_audit(
    db_client: TestClient, db_session: Session
) -> None:
    farmer, cid = _case(db_client, "rv-farmer@example.com")
    _, other_cid = _case(db_client, "rv-other@example.com")  # never requested: stays invisible
    expert = _expert(db_client, db_session, "rv-expert@example.com")

    assert db_client.get(f"{API}/review/queue", headers=farmer).status_code == 403
    assert db_client.get(f"{API}/review/queue", headers=expert).json() == []
    assert db_client.get(f"{API}/review/cases/{cid}", headers=expert).status_code == 404

    assert db_client.post(f"{API}/cases/{cid}/expert-review", headers=farmer).status_code == 204
    assert db_client.post(f"{API}/cases/{cid}/expert-review", headers=farmer).status_code == 409
    queue = db_client.get(f"{API}/review/queue", headers=expert).json()
    assert [q["case_id"] for q in queue] == [cid] and queue[0]["image_count"] == 1
    assert db_client.get(f"{API}/review/cases/{other_cid}", headers=expert).status_code == 404

    detail = db_client.get(f"{API}/review/cases/{cid}", headers=expert).json()
    assert detail["awaiting_review"] is True and detail["case"]["status"] == "expert_review"
    assert "sig=" in detail["case"]["submissions"][0]["images"][0]["url"]
    assert detail["case"]["analysis"]["result"] is None  # no model: nothing invented

    bad = db_client.post(
        f"{API}/review/cases/{cid}", headers=expert, json={"decision": "diagnosed"}
    )
    assert bad.status_code == 422  # a diagnosis needs a label
    ok = db_client.post(
        f"{API}/review/cases/{cid}",
        headers=expert,
        json={
            "decision": "diagnosed",
            "label": "Early blight",
            "note": "Concentric rings on lower leaves.",
        },
    )
    assert ok.status_code == 201 and ok.json()["expert_name"] == "Dr Agronomist"
    again = db_client.post(
        f"{API}/review/cases/{cid}", headers=expert, json={"decision": "cannot_determine"}
    )
    assert again.status_code == 409  # closed

    mine = db_client.get(f"{API}/cases/{cid}", headers=farmer).json()
    assert mine["status"] == "closed"
    assert [(r["decision"], r["label"], r["source"]) for r in mine["expert_reviews"]] == [
        ("diagnosed", "Early blight", "expert_review")
    ]
    assert db_client.get(f"{API}/review/cases/{cid}", headers=expert).status_code == 200  # history
    actions = set(
        db_session.scalars(select(AuditEvent.action).where(AuditEvent.entity_id.isnot(None)))
    )
    assert {"crop_health_case.expert_requested", "crop_health_case.expert_reviewed"} <= actions


def test_needs_retake_returns_case_to_farmer_and_only_owner_can_request(
    db_client: TestClient, db_session: Session
) -> None:
    farmer, cid = _case(db_client, "rt-farmer@example.com")
    stranger = register(db_client, "rt-stranger@example.com")
    assert db_client.post(f"{API}/cases/{cid}/expert-review", headers=stranger).status_code == 404
    expert = _expert(db_client, db_session, "rt-expert@example.com")
    db_client.post(f"{API}/cases/{cid}/expert-review", headers=farmer)
    r = db_client.post(
        f"{API}/review/cases/{cid}", headers=expert, json={"decision": "needs_retake"}
    )
    assert r.status_code == 201
    assert db_client.get(f"{API}/cases/{cid}", headers=farmer).json()["status"] == "retake"
    assert db_client.post(f"{API}/cases/{cid}/expert-review", headers=farmer).status_code == 204


def test_expert_explanation_route_follows_case_visibility(
    db_client: TestClient, db_session: Session
) -> None:
    farmer, cid = _case(db_client, "ex-farmer@example.com")
    expert = _expert(db_client, db_session, "ex-expert@example.com")
    url = f"{API}/review/cases/{cid}/explanation"
    assert db_client.get(url, headers=farmer).status_code == 403
    assert db_client.get(url, headers=expert).status_code == 404  # not requested yet
    db_client.post(f"{API}/cases/{cid}/expert-review", headers=farmer)
    body = db_client.get(url, headers=expert).json()
    assert body["available"] is False and body["reason"] == "no_completed_analysis"
