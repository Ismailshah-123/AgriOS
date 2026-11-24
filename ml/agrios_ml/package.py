"""Package a selected run for serving. Never overwrites an existing version directory.

python -m agrios_ml.package <run_dir> --metrics reports/<exp>/<run>/metrics.json
       --name crop_doctor_tomato --version 1.0.0 --out <packages_root>

Writes <out>/<name>/<version>/: model.onnx, cam_weights.npy (GAP+linear heads only),
golden/ (val images + torch logits for serving-parity tests), package.json (labels,
preprocessing, temperature, thresholds, checksums, data + split hashes, environment).
Thresholds come from VALIDATION only:
  threshold      = smallest calibrated confidence whose accepted-set accuracy on val
                   reaches `target_accept_acc` (selective prediction).
  ood_threshold  = energy score at the `ood_tpr` quantile of val (in-distribution) energies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import torch
from torch import nn

from agrios_ml import metrics as M
from agrios_ml.data.dataset import PREPROCESSING, eval_transform, read_split
from agrios_ml.nets import build_model
from agrios_ml.train import resolve


class ExportWrapper(nn.Module):
    def __init__(self, model: nn.Module, arch: str) -> None:
        super().__init__()
        self.m, self.arch = model, arch

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if self.arch == "small_cnn":
            f = self.m.features(x)
            return self.m.head(self.m.pool(f)), f
        f = self.m.features(x)
        return self.m.classifier(torch.flatten(self.m.avgpool(f), 1)), f


def cam_weights(model: nn.Module, arch: str) -> np.ndarray | None:
    if arch == "small_cnn":
        return model.head[2].weight.detach().cpu().numpy()  # type: ignore[index]
    if arch == "efficientnet_b0":
        return model.classifier[1].weight.detach().cpu().numpy()  # type: ignore[index]
    return None  # MobileNetV3 head has a hidden layer: CAM would not be exact


def energy(logits: np.ndarray, t: float) -> np.ndarray:
    z = logits / t
    m = z.max(1)
    return -(m + np.log(np.exp(z - m[:, None]).sum(1)))


def pick_threshold(probs: np.ndarray, y: np.ndarray, target: float) -> float:
    conf, ok = probs.max(1), probs.argmax(1) == y
    for t in np.round(np.arange(0.30, 0.995, 0.005), 3):
        m = conf >= t
        if m.sum() >= 20 and ok[m].mean() >= target:
            return float(t)
    return 0.99


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--metrics", type=Path, required=True)
    ap.add_argument("--name", default="crop_doctor_tomato")
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--target-accept-acc", type=float, default=0.99)
    ap.add_argument("--ood-tpr", type=float, default=0.95)
    a = ap.parse_args()
    dest = a.out / a.name / a.version
    if dest.exists():
        raise SystemExit(f"{dest} exists: versions are immutable, choose a new version")
    cfg = json.loads((a.run_dir / "config.json").read_text(encoding="utf-8"))
    cmap = json.loads(resolve(cfg["class_map"]).read_text(encoding="utf-8"))
    classes = cmap["classes"]
    met = json.loads(a.metrics.read_text(encoding="utf-8"))
    ck = torch.load(a.run_dir / "best.pt", map_location="cpu", weights_only=True)
    model = build_model(cfg["arch"], len(classes), pretrained=False)
    model.load_state_dict(ck["model"])
    model.eval()

    t = float(met["temperature"])
    vl, vy = np.load(a.run_dir / "val_logits.npy"), np.load(a.run_dir / "val_targets.npy")
    thr = pick_threshold(M.softmax(vl, t), vy, a.target_accept_acc)
    ood = float(np.quantile(energy(vl, t), a.ood_tpr))

    tmp = dest.with_name(dest.name + ".partial")
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "golden").mkdir(parents=True)
    wrapper = ExportWrapper(model, cfg["arch"]).eval()
    torch.onnx.export(
        wrapper,
        (torch.randn(1, 3, 224, 224),),
        tmp / "model.onnx",
        input_names=["image"],
        output_names=["logits", "features"],
        dynamic_axes={"image": {0: "n"}, "logits": {0: "n"}, "features": {0: "n"}},
        opset_version=17,
        dynamo=False,
    )
    cw = cam_weights(model, cfg["arch"])
    if cw is not None:
        np.save(tmp / "cam_weights.npy", cw.astype(np.float32))

    # Golden parity vectors: 6 validation images through the torch eval pipeline.
    from PIL import Image

    rows = read_split(resolve(cfg["split"]), classes, "val")[:: max(1, 1000)][:6]
    golden = []
    with torch.no_grad():
        for r in rows:
            src = resolve(cfg["cache"]) / f"{r['image_id']}.jpg"
            shutil.copy(src, tmp / "golden" / src.name)
            with Image.open(src) as im:
                x = eval_transform()(im.convert("RGB")).unsqueeze(0)
            golden.append({"file": src.name, "class": r["class"], "logits": model(x)[0].tolist()})
    (tmp / "golden" / "golden.json").write_text(json.dumps(golden), encoding="utf-8")

    split_path = resolve(cfg["split"])
    try:
        commit = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"],  # noqa: S607 - fixed args, read-only
                capture_output=True,
                text=True,
                cwd=resolve("."),
                check=False,
            ).stdout.strip()
            or None
        )
    except OSError:
        commit = None
    pkg = {
        "name": a.name,
        "version": a.version,
        "task": "crop_health_image",
        "framework": "onnx",
        "arch": cfg["arch"],
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "labels": [{"id": i, "label": c, "crop": cmap["crop"]} for i, c in enumerate(classes)],
        "supported_crops": [cmap["crop"]],
        "artifact": "model.onnx",
        "checksum_sha256": sha256(tmp / "model.onnx"),
        "cam_weights_file": "cam_weights.npy" if cw is not None else None,
        "preprocessing": PREPROCESSING,
        "temperature": round(t, 4),
        "threshold": thr,
        "ood_threshold": round(ood, 4),
        "threshold_policy": {
            "target_accept_acc_on_val": a.target_accept_acc,
            "ood_energy_quantile_on_val": a.ood_tpr,
        },
        "class_map_version": cmap["version"],
        "split_file": split_path.name,
        "split_sha256": sha256(split_path),
        "train_config": cfg,
        "source_checkpoint_sha256": sha256(a.run_dir / "best.pt"),
        "best_epoch": ck["epoch"],
        "metrics_summary": {
            k: {m: met[k][m] for m in ("n", "accuracy", "macro_f1", "ece_15")}
            for k in ("val", "val_calibrated", "test", "external_test")
            if k in met
        },
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "platform": platform.platform(),
        },
        "git_commit": commit,
        "pretrained_weights": None
        if cfg["arch"] == "small_cnn"
        else "torchvision ImageNet-1k (BSD-3 code; ImageNet terms: non-commercial research)",
    }
    (tmp / "package.json").write_text(json.dumps(pkg, indent=2), encoding="utf-8")
    tmp.replace(dest)
    print(
        json.dumps(
            {
                k: pkg[k]
                for k in (
                    "name",
                    "version",
                    "checksum_sha256",
                    "temperature",
                    "threshold",
                    "ood_threshold",
                )
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
