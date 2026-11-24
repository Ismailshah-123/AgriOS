"""GET /cases/{id}/explanation: owner-only CAM maps, never for out_of_scope (FR4).

Uses the worker tests' test-double predictor; no real model is involved, so these tests
check the contract and geometry only, not heatmap quality.
"""

import pytest

from app.crop_health.explanation import crop_box
from app.mlops import registry
from app.mlops.predictor import ModelInput, RawOutput
from tests.db.test_analysis_worker import env, install_model, work  # noqa: F401  (fixtures)
from tests.support import API, register

pytestmark = pytest.mark.db

PREP = {"resize_short_side": 256, "center_crop": 224, "mean": [0, 0, 0], "std": [1, 1, 1]}
GRID = [[0.0, 0.5], [1.0, 0.25]]


class CamDouble:
    def __init__(self, logits: list[float], with_maps: bool = True) -> None:
        self.logits, self.with_maps = logits, with_maps

    def predict(self, x: ModelInput) -> RawOutput:
        exp = {
            "method": "class_activation_map", "target_class": "Early blight",
            "maps": [{"image_index": 0, "grid": GRID}], "note": "An explanation aid.",
        }  # fmt: skip
        return RawOutput(logits=self.logits, explanation=exp if self.with_maps else None)


def _analyse(env: dict, monkeypatch: pytest.MonkeyPatch, logits: list[float], **kw: object) -> dict:  # noqa: F811
    mv = install_model(env, **kw)  # type: ignore[arg-type]
    mv.config = {"preprocessing": PREP}
    env["db"].flush()
    monkeypatch.setitem(registry.LOADERS, "test-double", lambda m, p: CamDouble(logits))
    work(env)
    return env["client"].get(f"{API}/cases/{env['case_id']}/explanation", headers=env["h"]).json()


def test_crop_box_matches_resize_then_centre_crop() -> None:
    assert crop_box(300, 200, PREP) == [0.2083, 0.0625, 0.5833, 0.875]  # landscape
    assert crop_box(200, 300, PREP) == [0.0625, 0.2083, 0.875, 0.5833]  # portrait
    assert crop_box(256, 256, PREP) == [0.0625, 0.0625, 0.875, 0.875]


def test_no_analysis_means_no_explanation(env: dict) -> None:  # noqa: F811
    body = env["client"].get(f"{API}/cases/{env['case_id']}/explanation", headers=env["h"]).json()
    assert body["available"] is False and body["reason"] == "no_completed_analysis"
    assert body["maps"] == []


def test_accepted_result_returns_signed_photo_grid_and_crop_box(env: dict, monkeypatch) -> None:  # noqa: ANN001, F811
    body = _analyse(env, monkeypatch, [0.0, 6.0, 1.0])
    assert body["available"] is True and body["decision"] == "accepted"
    assert (body["method"], body["target_class"]) == ("class_activation_map", "Early blight")
    (m,) = body["maps"]
    assert m["grid"] == GRID
    assert "sig=" in m["image"]["url"] and len(m["crop_box"]) == 4
    assert "Decision support only" in body["limits_note"]
    analysis = env["client"].get(f"{API}/cases/{env['case_id']}/analysis", headers=env["h"])
    assert analysis.json()["result"]["explanation_available"] is True


def test_out_of_scope_never_returns_a_map(env: dict, monkeypatch) -> None:  # noqa: ANN001, F811
    body = _analyse(env, monkeypatch, [0.0, 6.0, 1.0], ood="-10.0")
    assert body == {**body, "available": False, "reason": "out_of_scope", "maps": []}
    analysis = env["client"].get(f"{API}/cases/{env['case_id']}/analysis", headers=env["h"])
    assert analysis.json()["result"]["explanation_available"] is False


def test_other_users_get_404(env: dict, monkeypatch) -> None:  # noqa: ANN001, F811
    _analyse(env, monkeypatch, [0.0, 6.0, 1.0])
    other = register(env["client"], "cam-other@example.com")
    res = env["client"].get(f"{API}/cases/{env['case_id']}/explanation", headers=other)
    assert res.status_code == 404
