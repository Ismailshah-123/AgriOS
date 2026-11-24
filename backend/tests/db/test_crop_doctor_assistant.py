"""Crop Doctor AI assistant: the model's decision stays the diagnosis; the LLM (a scripted fake
here) only explains; the photo is sent only on opt-in; owner-only; doses removed."""

from __future__ import annotations

import pytest

from app.crop_health.focus import summarise
from app.knowledge import providers
from app.knowledge.providers import LLMReply
from tests.db.test_analysis_worker import FixedLogitsDouble, env, install_model, work  # noqa: F401
from tests.support import API, register

pytestmark = pytest.mark.db


class FakeLLM:
    provider, model = "fake", "vision-fake"

    def __init__(self, reply: str) -> None:
        self.reply, self.calls = reply, []

    def chat(self, messages, *, max_tokens, json_mode=False):  # noqa: ANN001, ANN201
        self.calls.append(messages)
        return LLMReply(self.reply, "fake", "vision-fake", 50, 20, 3)


REPLY = (
    '{"seen_in_photo": "Brown spots with rings on the lower leaf.",'
    ' "explanation": "The AgriOS model result is early blight [F].",'
    ' "next_steps": "Ask an expert to confirm. Do not spray 2 kg per acre of anything [F]."}'
)


@pytest.fixture
def analysed(env: dict, monkeypatch: pytest.MonkeyPatch) -> dict:  # noqa: F811
    from app.mlops import registry

    install_model(env)
    monkeypatch.setitem(
        registry.LOADERS, "test-double", lambda mv, p: FixedLogitsDouble([0.0, 6.0, 0.0])
    )
    assert work(env)
    yield env
    providers.set_llm_for_tests(None, active=False)


def test_assistant_explains_with_photo_opt_in_and_keeps_model_decision(analysed: dict) -> None:
    c, h, cid = analysed["client"], analysed["h"], analysed["case_id"]
    fake = FakeLLM(REPLY)
    providers.set_llm_for_tests(fake)
    r = c.post(
        f"{API}/cases/{cid}/assistant", headers=h, json={"language": "ur", "send_photo": True}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    user_msg = fake.calls[0][1]["content"]
    assert isinstance(user_msg, list) and user_msg[1]["image_url"]["url"].startswith(
        "data:image/jpeg"
    )
    assert "Model decision: accepted" in user_msg[0]["text"]
    assert "Urdu" in fake.calls[0][0]["content"]  # answer language requested
    assert body["meta"]["photo_sent"] is True and body["language"] == "ur"
    assert body["meta"]["sections"]["seen_in_photo"].startswith("Brown spots")
    assert "2 kg per acre" not in body["answer"] and "[rate removed]" in body["answer"]
    assert body["meta"]["case_record"]["model_result"]["decision"] == "accepted"
    hist = c.get(f"{API}/cases/{cid}/assistant", headers=h).json()
    assert [x["id"] for x in hist] == [body["id"]]
    # Without opt-in the photo never leaves the server.
    c.post(f"{API}/cases/{cid}/assistant", headers=h, json={"question": "How does it spread?"})
    assert isinstance(fake.calls[1][1]["content"], str)
    other = register(c, "other-assist@example.com")
    assert c.get(f"{API}/cases/{cid}/assistant", headers=other).status_code == 404
    assert c.post(f"{API}/cases/{cid}/assistant", headers=other, json={}).status_code == 404


def test_assistant_without_llm_and_without_diagnosis(env: dict) -> None:  # noqa: F811
    c, h, cid = env["client"], env["h"], env["case_id"]
    providers.set_llm_for_tests(None)
    try:
        r = c.post(f"{API}/cases/{cid}/assistant", headers=h, json={"send_photo": True}).json()
    finally:
        providers.set_llm_for_tests(None, active=False)
    assert r["status"] in ("abstained", "extractive")
    assert "llm_disabled" in r["meta"]["warnings"]
    assert "no_validated_diagnosis_expert_review_advised" in r["meta"]["warnings"]
    assert r["meta"]["photo_sent"] is False


def test_model_info_exposes_classes_and_no_invented_metrics(analysed: dict) -> None:
    info = analysed["client"].get(f"{API}/models/availability", headers=analysed["h"]).json()
    assert info["status"] == "ready" and info["supported_crops"] == ["tomato"]
    assert len(info["classes"]) == 3 and info["metrics_summary"] is None


def test_heatmap_focus_summary() -> None:
    g = [[0.0] * 7 for _ in range(7)]
    g[0][0], g[0][1], g[1][0] = 1.0, 0.7, 0.6
    f = summarise(g)
    assert f is not None and f["position"] == "upper left" and f["hotspots"] == 1
    assert f["strong_share_pct"] == 6 and "upper left" in f["text_en"] and f["text_ur"]
    assert summarise([[0.1, 0.2]]) is None


def test_out_of_scope_record_withholds_class_possibilities() -> None:
    from app.crop_health.assistant_context import _record_block

    rec = {
        "reference": "CD-000001", "crop": "tomato", "days_after_sowing": 30,
        "inference_status": "completed", "province": None, "district": None, "observations": [],
        "model_result": {
            "decision": "out_of_scope", "predicted_class": None, "calibrated_confidence": 0.9,
            "shortlist": [{"label": "late_blight", "probability": 0.9}], "model": "m 1.0.0",
        },
    }  # fmt: skip
    block = _record_block(rec, "en")
    assert "out of scope - NOT a diagnosis" in block
    assert "late blight" not in block.lower() and "90%" not in block
