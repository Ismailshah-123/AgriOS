"""ONNX Runtime predictor (framework "onnx"). CPU execution; no pickle/torch in the API.

Model package contract (written by ml/agrios_ml/package.py):
  - ONNX graph: input "image" float32 [N,3,H,W]; outputs "logits" [N,K] and
    "features" [N,C,h,w] (last conv feature map before global-average pooling).
  - model_versions.config["preprocessing"]: resize_short_side, center_crop, mean, std.
  - model_versions.config["cam_weights_file"]: .npy [K,C] classifier weights (GAP+linear
    head), so class activation maps are computed from the real model:
        CAM_c = ReLU(sum_k w_ck * A_k)  (Zhou et al. 2016; equals Grad-CAM for GAP+linear).
Logits are averaged over a submission's images; the decision rule stays in `decide()`.
"""

from __future__ import annotations

import io
import threading
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from app.mlops.models import ModelVersion
from app.mlops.predictor import ModelInput, RawOutput

_CACHE: dict[tuple[str, str], OnnxPredictor] = {}
_LOCK = threading.Lock()


def preprocess(data: bytes, cfg: dict[str, Any]) -> np.ndarray:
    """Byte-for-byte the same geometry as torchvision Resize(short, BICUBIC) + CenterCrop."""
    short, crop = int(cfg["resize_short_side"]), int(cfg["center_crop"])
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w <= h:
            nw, nh = short, int(short * h / w)
        else:
            nw, nh = int(short * w / h), short
        im = im.resize((nw, nh), Image.Resampling.BICUBIC)
        top, left = int(round((nh - crop) / 2.0)), int(round((nw - crop) / 2.0))
        im = im.crop((left, top, left + crop, top + crop))
        x = np.asarray(im, dtype=np.float32) / 255.0
    x = (x - np.array(cfg["mean"], np.float32)) / np.array(cfg["std"], np.float32)
    return x.transpose(2, 0, 1)


class OnnxPredictor:
    def __init__(self, model: ModelVersion, path: Path) -> None:
        import onnxruntime as ort

        so = ort.SessionOptions()
        so.intra_op_num_threads = 4
        self.session = ort.InferenceSession(str(path), so, providers=["CPUExecutionProvider"])
        self.cfg = model.config["preprocessing"]
        cam = model.config.get("cam_weights_file")
        if cam and Path(cam).name != cam:
            raise ValueError("cam_weights_file must be a bare file name")
        self.cam_w = np.load(path.parent / cam, allow_pickle=False) if cam else None
        self.labels = [lbl["label"] for lbl in model.labels]

    def predict(self, x: ModelInput) -> RawOutput:
        if not x.images:
            raise ValueError("no images")
        batch = np.stack([preprocess(b, self.cfg) for b in x.images])
        logits, feats = self.session.run(["logits", "features"], {"image": batch})
        mean_logits = logits.astype(np.float64).mean(0)
        explanation = None
        if self.cam_w is not None:
            top = int(mean_logits.argmax())
            maps = []
            for i in range(len(x.images)):
                cam = np.maximum(np.tensordot(self.cam_w[top], feats[i], axes=(0, 0)), 0)
                peak = float(cam.max())
                grid = (cam / peak).round(3).tolist() if peak > 0 else cam.tolist()
                maps.append({"image_index": i, "grid": grid})
            explanation = {
                "method": "class_activation_map",
                "target_class": self.labels[top],
                "maps": maps,
                "note": "Highlights regions that raised the score "
                "for this class; an explanation aid, not proof of the cause.",
            }
        return RawOutput(
            logits=[float(v) for v in mean_logits],
            explanation=explanation,
            extra={"per_image_top": [self.labels[int(i)] for i in logits.argmax(1)]},
        )


def load(model: ModelVersion, path: Path) -> OnnxPredictor:
    """Loaded once per (artefact, checksum) and reused across jobs."""
    key = (str(path), model.checksum_sha256)
    with _LOCK:
        if key not in _CACHE:
            _CACHE.clear()  # only one active model per task; drop the old session
            _CACHE[key] = OnnxPredictor(model, path)
        return _CACHE[key]
