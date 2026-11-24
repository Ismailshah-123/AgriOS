"""FR6: with no reviewed table the API refuses, escalates and returns no numbers."""

import pytest
from fastapi.testclient import TestClient

from tests.support import API, create_cycle, create_farm, create_field, register

pytestmark = pytest.mark.db


def test_refuses_without_reviewed_source_and_is_owner_scoped(db_client: TestClient) -> None:
    h = register(db_client, "fert@example.com")
    field = create_field(db_client, h, create_farm(db_client, h)["id"])
    cid = create_cycle(db_client, h, field["id"], status="active", sowing_date="2026-10-01")["id"]
    r = db_client.get(f"{API}/crop-cycles/{cid}/fertilizer", headers=h)
    body = r.json()
    assert r.status_code == 200
    assert (body["status"], body["reason"], body["escalation"]) == (
        "refused", "no_reviewed_source", "expert_review")  # fmt: skip
    assert body["doses"] is None
    assert not any(ch.isdigit() for ch in body["message"])  # no number of any kind
    other = register(db_client, "fert-other@example.com")
    assert db_client.get(f"{API}/crop-cycles/{cid}/fertilizer", headers=other).status_code == 404
