"""Inference pipeline through the real job queue and worker.

The predictor used here is a TEST DOUBLE that returns fixed logits; it exists only in this
test module and is registered through the same loader registry a real PyTorch loader will
use. It validates the contract, not any model quality.
"""

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.crop_health.models import CropHealthAnalysis, CropHealthCase
from app.db.session import get_db
from app.jobs import queue
from app.jobs.models import Job
from app.jobs.worker import run_once
from app.main import create_app
from app.mlops import registry
from app.mlops.models import ModelStatus, ModelVersion
from app.mlops.predictor import ModelInput, RawOutput
from tests.images import make_image
from tests.support import API, create_cycle, create_farm, create_field, register

pytestmark = pytest.mark.db
LABELS = [
    {"id": 0, "label": "Healthy", "crop": "tomato"},
    {"id": 1, "label": "Early blight", "crop": "tomato"},
    {"id": 2, "label": "Late blight", "crop": "tomato"},
]


class FixedLogitsDouble:
    """Test double: deterministic logits, or a raised error, to exercise the contract."""

    def __init__(self, logits: list[float] | Exception) -> None:
        self.logits = logits
        self.seen: list[ModelInput] = []

    def predict(self, x: ModelInput) -> RawOutput:
        self.seen.append(x)
        if isinstance(self.logits, Exception):
            raise self.logits
        return RawOutput(logits=self.logits)


@pytest.fixture
def env(db_settings: Settings, db_session: Session, tmp_path: Path) -> Iterator[dict]:
    settings = db_settings.model_copy(
        update={"storage_path": tmp_path / "up", "model_path": tmp_path / "models"}
    )
    app = create_app(settings)
    app.dependency_overrides[get_db] = lambda: db_session
    with TestClient(app, raise_server_exceptions=False) as client:
        h = register(client, "worker@example.com")
        field = create_field(client, h, create_farm(client, h)["id"])
        cycle = create_cycle(client, h, field["id"], status="active", sowing_date="2026-10-01")
        res = client.post(
            f"{API}/cases",
            headers=h,
            data={"crop_cycle_id": cycle["id"]},
            files=[("images", ("a.jpg", make_image(), "image/jpeg"))],
        )
        assert res.status_code == 201
        yield {
            "client": client,
            "h": h,
            "case_id": res.json()["id"],
            "settings": settings,
            "storage": app.state.storage,
            "db": db_session,
        }


def install_model(
    env: dict,
    *,
    threshold: str | None = "0.70",
    ood: str | None = "0.0",
    write_file: bool = True,
    checksum: str | None = None,
    framework: str = "test-double",
) -> ModelVersion:
    root: Path = env["settings"].model_path
    root.mkdir(parents=True, exist_ok=True)
    blob = b"fake-weights-for-contract-test"
    if write_file:
        (root / "tomato.bin").write_bytes(blob)
    mv = ModelVersion(
        task=registry.CROP_HEALTH_TASK,
        name="tomato-test",
        version="0.0.1",
        framework=framework,
        arch="test",
        labels=LABELS,
        supported_crops=["tomato"],
        artifact_uri="tomato.bin",
        checksum_sha256=checksum or hashlib.sha256(blob).hexdigest(),
        temperature=Decimal("1.0"),
        threshold=Decimal(threshold) if threshold else None,
        ood_threshold=Decimal(ood) if ood else None,
        status=ModelStatus.ACTIVE,
    )
    env["db"].add(mv)
    env["db"].flush()
    return mv


def work(env: dict) -> bool:
    return run_once(env["db"], env["storage"], env["settings"], "test-worker")


def case(env: dict) -> dict:
    return env["client"].get(f"{API}/cases/{env['case_id']}", headers=env["h"]).json()


def predictions(env: dict) -> int:
    return env["db"].scalar(select(func.count()).select_from(CropHealthAnalysis)) or 0


@pytest.fixture
def double(monkeypatch: pytest.MonkeyPatch):  # noqa: ANN201
    def _use(logits: list[float] | Exception) -> FixedLogitsDouble:
        d = FixedLogitsDouble(logits)
        monkeypatch.setitem(registry.LOADERS, "test-double", lambda mv, path: d)
        return d

    return _use


# --------------------------------------------------------------- availability


def test_no_model_marks_case_model_unavailable_without_any_prediction(env: dict) -> None:
    assert work(env) is True
    c = case(env)
    assert c["inference_status"] == "model_unavailable"
    assert c["status"] == "submitted"
    assert c["analysis"]["model_availability"] == "not_registered"
    assert c["analysis"]["result"] is None and c["analysis"]["can_retry"] is True
    assert predictions(env) == 0
    assert work(env) is False  # job finished; nothing left


@pytest.mark.parametrize(
    ("kwargs", "status"),
    [
        ({"write_file": False}, "not_installed"),
        ({"checksum": "0" * 64}, "checksum_mismatch"),
        ({"framework": "pytorch"}, "error"),
    ],
    ids=["missing-file", "bad-checksum", "no-runtime"],
)
def test_model_availability_is_decided_from_facts(env: dict, kwargs: dict, status: str) -> None:
    install_model(env, **kwargs)
    work(env)
    c = case(env)
    assert c["analysis"]["model_availability"] == status
    assert c["inference_status"] == "model_unavailable"
    assert predictions(env) == 0
    avail = env["client"].get(f"{API}/models/availability", headers=env["h"]).json()
    assert avail["status"] == status


# ------------------------------------------------------------------ decisions


def test_confident_in_distribution_result_is_accepted_with_model_version(env: dict, double) -> None:  # noqa: ANN001
    mv = install_model(env)
    d = double([0.0, 6.0, 1.0])
    work(env)
    c = case(env)
    assert (c["inference_status"], c["status"]) == ("completed", "accepted")
    r = c["analysis"]["result"]
    assert r["predicted_class"] == "Early blight"
    assert r["calibrated_confidence"] > 0.9
    assert (r["model_name"], r["model_version"]) == ("tomato-test", "0.0.1")
    assert "Decision support only" in r["limits_note"]
    assert [s["label"] for s in r["shortlist"]][0] == "Early blight"
    row = env["db"].scalar(select(CropHealthAnalysis))
    assert row.model_version_id == mv.id
    assert d.seen[0].crop_code == "tomato" and len(d.seen[0].images) == 1


def test_low_confidence_is_unsure_and_hides_the_class(env: dict, double) -> None:  # noqa: ANN001
    install_model(env)
    double([1.0, 1.2, 1.1])
    work(env)
    r = case(env)["analysis"]["result"]
    assert r["decision"] == "unsure" and r["predicted_class"] is None


def test_out_of_distribution_input_is_out_of_scope(env: dict, double) -> None:  # noqa: ANN001
    install_model(env, ood="-10.0")  # energy of these logits is about -6: above threshold
    double([0.0, 6.0, 1.0])
    work(env)
    r = case(env)["analysis"]["result"]
    assert r["decision"] == "out_of_scope" and r["predicted_class"] is None


def test_uncalibrated_model_can_never_produce_an_accepted_result(env: dict, double) -> None:  # noqa: ANN001
    install_model(env, threshold=None, ood=None)
    double([0.0, 50.0, 0.0])
    work(env)
    assert case(env)["analysis"]["result"]["decision"] == "unsure"


def test_unsupported_crop_is_not_analysed(env: dict, double) -> None:  # noqa: ANN001
    mv = install_model(env)
    mv.supported_crops = ["wheat"]
    env["db"].flush()
    d = double([0.0, 6.0, 1.0])
    work(env)
    c = case(env)
    assert c["inference_status"] == "model_unavailable"
    assert c["analysis"]["error_code"] == "crop_not_supported"
    assert "does not support this crop" in c["analysis"]["message"]
    assert "No validated analysis model" not in c["analysis"]["message"]
    assert d.seen == [] and predictions(env) == 0


# ------------------------------------------------------------- failure handling


@pytest.mark.parametrize(
    "bad",
    [RuntimeError("cuda exploded"), [1.0, 2.0], [float("nan"), 1, 2]],
    ids=["raises", "wrong-length", "nan"],
)
def test_failures_retry_then_fail_without_corrupting_the_case(env: dict, double, bad) -> None:  # noqa: ANN001
    install_model(env)
    double(bad)
    job = env["db"].scalar(select(Job))
    for attempt in range(1, 4):
        job.run_after = datetime.now(UTC) - timedelta(seconds=1)  # skip backoff in tests
        env["db"].flush()
        assert work(env) is True
        c = case(env)
        expected = "queued" if attempt < 3 else "failed"
        assert c["inference_status"] == expected, attempt
    assert c["status"] == "submitted"
    assert c["analysis"]["result"] is None and c["analysis"]["can_retry"] is True
    assert c["analysis"]["error_code"].startswith("inference_error:")
    assert "exploded" not in str(c)  # internal messages are not exposed
    assert predictions(env) == 0
    assert c["image_count"] == 1  # photos untouched
    assert env["db"].scalar(select(Job)).status == "failed"


def test_claim_is_exclusive_and_duplicates_are_suppressed(env: dict) -> None:
    db = env["db"]
    assert (
        queue.enqueue(
            db,
            kind="crop_health.analyse",
            dedupe_key=f"case:{env['case_id']}",
            payload={"case_id": env["case_id"]},
        )
        is None
    )
    first = queue.claim(db, "w1", ["crop_health.analyse"])
    assert first is not None
    assert queue.claim(db, "w2", ["crop_health.analyse"]) is None  # already running
    first.started_at = datetime.now(UTC) - timedelta(hours=1)  # worker died
    db.flush()
    reclaimed = queue.claim(db, "w3", ["crop_health.analyse"])
    assert reclaimed is not None and reclaimed.locked_by == "w3" and reclaimed.attempts == 2


def test_retry_endpoint_requeues_after_model_unavailable(env: dict, double) -> None:  # noqa: ANN001
    work(env)  # -> model_unavailable
    install_model(env)
    double([0.0, 6.0, 1.0])
    res = env["client"].post(f"{API}/cases/{env['case_id']}/analysis/retry", headers=env["h"])
    assert res.status_code == 200 and res.json()["inference_status"] == "queued"
    work(env)
    assert case(env)["inference_status"] == "completed"
    assert env["db"].get(CropHealthCase, env["case_id"]).status == "accepted"
