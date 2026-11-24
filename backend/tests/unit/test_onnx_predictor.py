"""ONNX serving tests. The parity test runs against a real packaged model when
AGRIOS_TEST_MODEL_PACKAGE points at one (golden logits produced by the torch pipeline)."""

import io
import json
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from PIL import Image

from app.mlops import registry
from app.mlops.onnx_predictor import OnnxPredictor, preprocess
from app.mlops.predictor import ModelInput, decide

CFG = {
    "resize_short_side": 256,
    "center_crop": 224,
    "mean": [0.485, 0.456, 0.406],
    "std": [0.229, 0.224, 0.225],
}


def _img(w: int, h: int, color: tuple[int, int, int] = (40, 160, 60)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "WEBP")
    return buf.getvalue()


def test_preprocess_geometry_and_normalisation() -> None:
    for w, h in ((320, 240), (240, 320), (2048, 1536), (256, 256)):
        x = preprocess(_img(w, h), CFG)
        assert x.shape == (3, 224, 224) and x.dtype == np.float32
    x = preprocess(_img(300, 300, (124, 116, 104)), CFG)
    assert abs(float(x.mean())) < 0.05  # ImageNet mean colour -> ~0 after normalisation


def test_onnx_loader_registered() -> None:
    assert "onnx" in registry.LOADERS


def test_cam_file_must_be_bare_name(tmp_path: Path) -> None:
    mv = SimpleNamespace(
        config={"preprocessing": CFG, "cam_weights_file": "../x.npy"},
        labels=[],
        checksum_sha256="0",
    )
    with pytest.raises(Exception):  # noqa: B017 - onnxruntime or our ValueError
        OnnxPredictor(mv, tmp_path / "missing.onnx")  # type: ignore[arg-type]


PKG = os.environ.get("AGRIOS_TEST_MODEL_PACKAGE")


@pytest.mark.skipif(not PKG, reason="AGRIOS_TEST_MODEL_PACKAGE not set (no packaged model)")
def test_serving_parity_with_training_pipeline() -> None:
    pkg_dir = Path(PKG or "")
    pkg = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
    mv = SimpleNamespace(
        config={"preprocessing": pkg["preprocessing"], "cam_weights_file": pkg["cam_weights_file"]},
        labels=pkg["labels"],
        checksum_sha256=pkg["checksum_sha256"],
    )
    p = OnnxPredictor(mv, pkg_dir / pkg["artifact"])  # type: ignore[arg-type]
    labels = [lbl["label"] for lbl in pkg["labels"]]
    for g in json.loads((pkg_dir / "golden" / "golden.json").read_text(encoding="utf-8")):
        raw = p.predict(
            ModelInput(images=[(pkg_dir / "golden" / g["file"]).read_bytes()], crop_code="tomato")
        )
        assert np.allclose(raw.logits, g["logits"], atol=2e-3), g["file"]
        d = decide(raw, labels, pkg["temperature"], pkg["threshold"], pkg["ood_threshold"])
        assert abs(sum(d.probs.values()) - 1) < 1e-3
        if raw.explanation:
            grid = np.array(raw.explanation["maps"][0]["grid"])
            assert grid.ndim == 2 and grid.max() <= 1.0 + 1e-6
