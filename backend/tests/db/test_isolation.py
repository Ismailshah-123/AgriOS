"""Cross-user isolation: changing an id in a request must never expose or modify
another farmer's records. Every case answers 404 (not 403) so existence is hidden."""

import pytest
from fastapi.testclient import TestClient

from tests.support import API, create_cycle, create_farm, create_field, crop_id, register

pytestmark = pytest.mark.db


@pytest.fixture
def two_users(db_client: TestClient) -> dict:
    alice = register(db_client, "alice@example.com", "Alice")
    bob = register(db_client, "bob@example.com", "Bob")
    farm = create_farm(db_client, alice, "Alice Farm")
    field = create_field(db_client, alice, farm["id"])
    cycle = create_cycle(db_client, alice, field["id"])
    return {"alice": alice, "bob": bob, "farm": farm, "field": field, "cycle": cycle}


RESOURCES = [("farms", "farm"), ("fields", "field"), ("crop-cycles", "cycle")]
PATCHES = {"farm": {"name": "Hijacked"}, "field": {"name": "Hijacked"}, "cycle": {"variety": "X"}}


@pytest.mark.parametrize(("path", "key"), RESOURCES)
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_other_users_record_is_404(
    db_client: TestClient, two_users: dict, path: str, key: str, method: str
) -> None:
    url = f"{API}/{path}/{two_users[key]['id']}"
    kwargs = {"json": PATCHES[key]} if method == "patch" else {}
    res = getattr(db_client, method)(url, headers=two_users["bob"], **kwargs)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"
    # The owner's record is unchanged and still there.
    mine = db_client.get(url, headers=two_users["alice"])
    assert mine.status_code == 200
    assert mine.json().get("name") != "Hijacked"
    assert mine.json().get("variety") != "X"


def test_cannot_attach_children_to_other_users_parents(
    db_client: TestClient, two_users: dict
) -> None:
    bob = two_users["bob"]
    res = db_client.post(
        f"{API}/fields",
        headers=bob,
        json={
            "farm_id": two_users["farm"]["id"],
            "name": "Sneaky",
            "area": {"value": "1", "unit": "ha"},
        },
    )
    assert res.status_code == 404
    assert res.json()["error"]["field"] == "farm_id"
    res = db_client.post(
        f"{API}/crop-cycles",
        headers=bob,
        json={"field_id": two_users["field"]["id"], "crop_id": crop_id(db_client, bob)},
    )
    assert res.status_code == 404
    assert res.json()["error"]["field"] == "field_id"


@pytest.mark.parametrize("path", ["farms", "fields", "crop-cycles"])
def test_lists_and_filters_never_include_other_users_records(
    db_client: TestClient, two_users: dict, path: str
) -> None:
    bob = two_users["bob"]
    assert db_client.get(f"{API}/{path}", headers=bob).json()["items"] == []
    if path != "farms":
        filtered = db_client.get(
            f"{API}/{path}", headers=bob, params={"farm_id": two_users["farm"]["id"]}
        )
        assert filtered.json()["items"] == []


@pytest.mark.parametrize("path", ["farms", "fields", "crop-cycles", "crops"])
def test_endpoints_require_authentication(db_client: TestClient, path: str) -> None:
    assert db_client.get(f"{API}/{path}").status_code == 401
