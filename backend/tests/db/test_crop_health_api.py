"""Crop Doctor API against the isolated test database and a temporary private storage."""

import io
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.crop_health.models import CaseImage, CropHealthCase, InferenceStatus
from app.db.session import get_db
from app.jobs.models import Job
from app.main import create_app
from app.storage.base import StorageError
from app.storage.local import LocalFileStorage
from tests.images import make_image
from tests.support import API, create_cycle, create_farm, create_field, register

pytestmark = pytest.mark.db


@pytest.fixture
def make_client(db_settings: Settings, db_session: Session, tmp_path: Path):  # noqa: ANN201
    def _make(**overrides: object) -> tuple[TestClient, LocalFileStorage]:
        app: FastAPI = create_app(
            db_settings.model_copy(
                update={
                    "storage_path": tmp_path / "uploads",
                    "model_path": tmp_path / "models",
                    **overrides,
                }
            )
        )
        app.dependency_overrides[get_db] = lambda: db_session
        return TestClient(app, raise_server_exceptions=False), app.state.storage

    return _make


@pytest.fixture
def ch(make_client) -> Iterator[tuple[TestClient, LocalFileStorage]]:  # noqa: ANN001
    client, storage = make_client()
    with client:
        yield client, storage


def farmer(client: TestClient, email: str, status: str = "active") -> tuple[dict, str]:
    h = register(client, email)
    field = create_field(client, h, create_farm(client, h)["id"])
    cycle = create_cycle(client, h, field["id"], status=status, sowing_date="2026-10-01")
    return h, cycle["id"]


def photos(*blobs: bytes) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("images", (f"p{i}.jpg", b, "image/jpeg")) for i, b in enumerate(blobs)]


def submit(client: TestClient, h: dict, cycle_id: str, files: list, **form: object):  # noqa: ANN201
    data = {"crop_cycle_id": cycle_id, **form}
    return client.post(f"{API}/cases", headers=h, data=data, files=files)


# ----------------------------------------------------------------------- create


def test_create_case_stores_private_stripped_images_and_queues_analysis(
    ch: tuple[TestClient, LocalFileStorage], db_session: Session
) -> None:
    client, storage = ch
    h, cycle_id = farmer(client, "c1@example.com")
    res = submit(
        client,
        h,
        cycle_id,
        photos(make_image(gps=True), make_image("PNG")),
        plant_part="leaf",
        symptoms=["spots", "yellowing", "spots"],
        observed_on="2026-11-20",
        notes="Brown spots on lower leaves",
    )
    assert res.status_code == 201, res.text
    case = res.json()
    assert case["reference"] == "CD-000001"
    assert (case["status"], case["inference_status"]) == ("submitted", "queued")
    assert case["analysis"]["result"] is None
    assert case["analysis"]["model_availability"] == "not_registered"
    sub = case["submissions"][0]
    assert sub["kind"] == "initial"
    assert sub["symptoms"] == ["spots", "yellowing"]
    assert len(sub["images"]) == 2
    assert "storage_key" not in res.text and "crop-health/" not in res.text
    # Signed link works without a token and serves EXIF-free WebP.
    img = client.get(sub["images"][0]["url"])
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/webp"
    assert img.headers["x-content-type-options"] == "nosniff"
    assert not Image.open(io.BytesIO(img.content)).getexif()
    assert b"SecretPhoneMaker" not in img.content
    assert len(storage.list("crop-health")) == 4  # full + thumb per photo
    jobs = db_session.scalars(select(Job).where(Job.dedupe_key == f"case:{case['id']}")).all()
    assert [j.status for j in jobs] == ["queued"]


def test_case_requires_an_active_owned_cycle(ch: tuple[TestClient, LocalFileStorage]) -> None:
    client, _ = ch
    h, planned = farmer(client, "c2@example.com", status="planned")
    res = submit(client, h, planned, photos(make_image()))
    assert res.status_code == 422 and res.json()["error"]["code"] == "cycle_not_active"
    other_h, other_cycle = farmer(client, "c2b@example.com")
    res = submit(client, h, other_cycle, photos(make_image()))
    assert res.status_code == 404


@pytest.mark.parametrize(
    ("files", "code"),
    [
        ([], "validation_error"),
        ([make_image()] * 6, "image_count"),
        ([make_image(), b"<html>not an image</html>"], "image_unreadable"),
        ([make_image("GIF")], "image_type_not_allowed"),
    ],
    ids=["none", "too-many", "fake-image", "gif"],
)
def test_upload_validation(
    ch: tuple[TestClient, LocalFileStorage], db_session: Session, files: list[bytes], code: str
) -> None:
    client, storage = ch
    h, cycle_id = farmer(client, f"v{len(files)}{code}@example.com")
    res = submit(client, h, cycle_id, photos(*files))
    assert res.status_code == 422
    assert res.json()["error"]["code"] == code
    if code == "image_unreadable":
        assert res.json()["error"]["message"].startswith("Photo 2:")
    assert storage.list("crop-health") == []
    assert db_session.scalar(select(func.count()).select_from(CropHealthCase)) == 0


def test_oversized_body_rejected_while_streaming(make_client) -> None:  # noqa: ANN001
    client, storage = make_client(upload_max_bytes=256 * 1024, upload_max_images=1)
    with client:
        h, cycle_id = farmer(client, "big@example.com")
        res = submit(client, h, cycle_id, photos(b"\xff\xd8" + b"0" * (2 * 1024 * 1024)))
    assert res.status_code == 413
    assert res.json()["error"]["code"] == "payload_too_large"


def test_storage_failure_leaves_no_case(
    make_client, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, storage = make_client()
    with client:
        h, cycle_id = farmer(client, "sf@example.com")
        calls = {"n": 0}
        real_put = storage.put

        def flaky(key: str, data: bytes, ct: str) -> None:
            calls["n"] += 1
            if calls["n"] == 3:
                raise StorageError("disk full")
            real_put(key, data, ct)

        monkeypatch.setattr(storage, "put", flaky)
        res = submit(client, h, cycle_id, photos(make_image(), make_image()))
    assert res.status_code == 503 and res.json()["error"]["code"] == "storage_unavailable"
    assert storage.list("crop-health") == []  # the 2 objects written first were removed
    assert db_session.scalar(select(func.count()).select_from(CropHealthCase)) == 0


def test_database_failure_after_storing_removes_files(
    make_client,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,  # noqa: ANN001
) -> None:
    client, storage = make_client()
    with client:
        h, cycle_id = farmer(client, "dbf@example.com")
        from app.crop_health import service

        def boom(*a: object, **k: object) -> None:
            raise RuntimeError("simulated database failure")

        monkeypatch.setattr(service.audit, "record", boom)
        res = submit(client, h, cycle_id, photos(make_image()))
    assert res.status_code == 500 and res.json()["error"]["code"] == "internal_error"
    assert "simulated" not in res.text
    assert storage.list("crop-health") == []
    assert db_session.scalar(select(func.count()).select_from(CropHealthCase)) == 0


def test_client_id_makes_offline_retries_idempotent(
    ch: tuple[TestClient, LocalFileStorage],
) -> None:
    client, storage = ch
    h, cycle_id = farmer(client, "idem@example.com")
    first = submit(client, h, cycle_id, photos(make_image()), client_id="offline-0001")
    second = submit(client, h, cycle_id, photos(make_image()), client_id="offline-0001")
    assert first.json()["id"] == second.json()["id"]
    assert len(storage.list("crop-health")) == 2


def test_quota_and_rate_limits(make_client) -> None:  # noqa: ANN001
    client, _ = make_client(storage_quota_bytes_per_user=1024 * 1024, case_create_limit_per_hour=2)
    with client:
        h, cycle_id = farmer(client, "limits@example.com")
        assert submit(client, h, cycle_id, photos(make_image())).status_code == 201
        assert submit(client, h, cycle_id, photos(make_image())).status_code == 201
        res = submit(client, h, cycle_id, photos(make_image()))
        assert res.status_code == 429
    client2, _ = make_client(storage_quota_bytes_per_user=1024 * 1024)
    with client2:
        h2, cycle2 = farmer(client2, "quota@example.com")
        noisy = Image.effect_noise((1800, 1800), 100).convert("RGB")
        buf = io.BytesIO()
        noisy.save(buf, format="PNG")
        res = submit(client2, h2, cycle2, photos(buf.getvalue()))
        assert res.status_code == 422 and res.json()["error"]["code"] == "storage_quota_exceeded"


# ----------------------------------------------------- list, detail, follow-up


def test_list_filters_search_and_pagination(ch: tuple[TestClient, LocalFileStorage]) -> None:
    client, _ = ch
    h, cycle_id = farmer(client, "list@example.com")
    ids = [submit(client, h, cycle_id, photos(make_image())).json()["id"] for _ in range(3)]
    page1 = client.get(f"{API}/cases", headers=h, params={"limit": 2}).json()
    page2 = client.get(
        f"{API}/cases", headers=h, params={"limit": 2, "cursor": page1["next_cursor"]}
    ).json()
    seen = [c["id"] for c in page1["items"] + page2["items"]]
    assert sorted(seen) == sorted(ids) and page2["next_cursor"] is None
    assert page1["items"][0]["thumb_url"].startswith(f"{API}/files/case-images/")
    found = client.get(f"{API}/cases", headers=h, params={"q": "CD-000002"}).json()["items"]
    assert [c["reference"] for c in found] == ["CD-000002"]
    queued = client.get(f"{API}/cases", headers=h, params={"inference_status": "queued"}).json()
    assert len(queued["items"]) == 3
    assert (
        client.get(f"{API}/cases", headers=h, params={"needs_follow_up": True}).json()["items"]
        == []
    )
    stats = client.get(f"{API}/cases/summary", headers=h).json()
    assert (stats["total"], stats["awaiting_analysis"], stats["needs_follow_up"]) == (3, 3, 0)


def test_follow_up_appends_history_and_requeues_once(
    ch: tuple[TestClient, LocalFileStorage], db_session: Session
) -> None:
    client, _ = ch
    h, cycle_id = farmer(client, "fu@example.com")
    case = submit(client, h, cycle_id, photos(make_image())).json()
    url = f"{API}/cases/{case['id']}/follow-ups"
    empty = client.post(url, headers=h, data={})
    assert empty.status_code == 422 and empty.json()["error"]["code"] == "empty_follow_up"
    note = client.post(url, headers=h, data={"notes": "Spots spreading", "symptoms": ["wilting"]})
    assert note.status_code == 201
    res = client.post(url, headers=h, files=photos(make_image("WEBP")), data={"plant_part": "leaf"})
    detail = res.json()
    assert [s["kind"] for s in detail["submissions"]] == ["initial", "follow_up", "follow_up"]
    assert detail["submissions"][1]["notes"] == "Spots spreading"
    assert detail["image_count"] == 2 and detail["submission_count"] == 3
    assert [e["kind"] for e in detail["timeline"]][:3] == ["created", "follow_up", "follow_up"]
    active = db_session.scalar(
        select(func.count())
        .select_from(Job)
        .where(Job.dedupe_key == f"case:{case['id']}", Job.status.in_(["queued", "running"]))
    )
    assert active == 1  # dedupe: still a single pending analysis


def test_retry_only_when_failed_or_model_unavailable(
    ch: tuple[TestClient, LocalFileStorage], db_session: Session
) -> None:
    client, _ = ch
    h, cycle_id = farmer(client, "retry@example.com")
    case = submit(client, h, cycle_id, photos(make_image())).json()
    url = f"{API}/cases/{case['id']}/analysis/retry"
    assert client.post(url, headers=h).status_code == 409
    row = db_session.get(CropHealthCase, case["id"])
    row.inference_status = InferenceStatus.MODEL_UNAVAILABLE
    db_session.execute(Job.__table__.update().values(status="succeeded"))
    db_session.flush()
    res = client.post(url, headers=h)
    assert res.status_code == 200 and res.json()["inference_status"] == "queued"


# ------------------------------------------------------------------ isolation


def test_other_users_cannot_reach_cases_or_images(ch: tuple[TestClient, LocalFileStorage]) -> None:
    client, _ = ch
    h, cycle_id = farmer(client, "owner@example.com")
    case = submit(client, h, cycle_id, photos(make_image())).json()
    img = case["submissions"][0]["images"][0]
    bob = register(client, "intruder@example.com")
    cid = case["id"]
    for method, path in [
        ("get", f"/cases/{cid}"),
        ("get", f"/cases/{cid}/analysis"),
        ("post", f"/cases/{cid}/analysis/retry"),
        ("post", f"/cases/{cid}/follow-ups"),
    ]:
        kwargs = {"data": {"notes": "x"}} if path.endswith("follow-ups") else {}
        res = getattr(client, method)(f"{API}{path}", headers=bob, **kwargs)
        assert res.status_code == 404, path
    assert client.get(f"{API}/cases", headers=bob).json()["items"] == []
    assert client.get(f"{API}/cases/summary", headers=bob).json()["total"] == 0
    # Tampered or expired links: always the same 404.
    tampered = img["url"].replace(img["id"], "00000000-0000-0000-0000-000000000000")
    assert client.get(tampered).status_code == 404
    assert client.get(img["url"].replace("/full?", "/thumb?")).status_code == 404
    expired = img["url"].split("?")[0] + "?exp=1&sig=" + "0" * 64
    assert client.get(expired).status_code == 404


def test_endpoints_require_authentication(ch: tuple[TestClient, LocalFileStorage]) -> None:
    client, _ = ch
    for path in ["/cases", "/cases/summary", "/models/availability"]:
        assert client.get(f"{API}{path}").status_code == 401
    assert client.post(f"{API}/cases").status_code == 401


def test_images_are_counted_in_db(
    ch: tuple[TestClient, LocalFileStorage], db_session: Session
) -> None:
    client, _ = ch
    h, cycle_id = farmer(client, "count@example.com")
    submit(client, h, cycle_id, photos(make_image(), make_image()))
    assert db_session.scalar(select(func.count()).select_from(CaseImage)) == 2


def test_closed_case_rejects_follow_ups(
    ch: tuple[TestClient, LocalFileStorage], db_session: Session
) -> None:
    client, _ = ch
    h, cycle_id = farmer(client, "closed@example.com")
    case = submit(client, h, cycle_id, photos(make_image())).json()
    db_session.get(CropHealthCase, case["id"]).status = "closed"
    db_session.flush()
    res = client.post(f"{API}/cases/{case['id']}/follow-ups", headers=h, data={"notes": "late"})
    assert res.status_code == 409 and res.json()["error"]["code"] == "case_closed"


def test_sweeper_removes_only_old_unreferenced_objects(
    ch: tuple[TestClient, LocalFileStorage], db_session: Session
) -> None:
    from datetime import timedelta

    from app.crop_health.service import sweep_orphans

    client, storage = ch
    h, cycle_id = farmer(client, "sweep@example.com")
    submit(client, h, cycle_id, photos(make_image()))
    storage.put("crop-health/2020/01/orphan-full.webp", b"x", "image/webp")
    assert sweep_orphans(db_session, storage, older_than=timedelta(hours=1)) == 0  # too new
    assert sweep_orphans(db_session, storage, older_than=timedelta(seconds=-1)) == 1
    keys = [o.key for o in storage.list("crop-health")]
    assert "crop-health/2020/01/orphan-full.webp" not in keys and len(keys) == 2
