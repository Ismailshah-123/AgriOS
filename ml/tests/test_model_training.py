import csv
import json
from pathlib import Path

import numpy as np
import pytest
import torch
from PIL import Image

from agrios_ml import metrics as M
from agrios_ml.data.dataset import eval_transform, train_transform
from agrios_ml.nets import build_model, count_params
from agrios_ml.train import check_worker_memory, run


def test_output_shapes_for_all_archs() -> None:
    x = torch.randn(2, 3, 224, 224)
    for arch in ("small_cnn", "efficientnet_b0", "mobilenet_v3_large"):
        m = build_model(arch, 10, pretrained=False).eval()
        assert m(x).shape == (2, 10)
    assert 1_000_000 < count_params(build_model("small_cnn", 10)) < 6_000_000


def test_transforms_shapes_and_eval_is_deterministic() -> None:
    im = Image.new("RGB", (320, 240), (40, 160, 60))
    a, b = eval_transform()(im), eval_transform()(im)
    assert a.shape == (3, 224, 224) and torch.equal(a, b)
    assert train_transform()(im).shape == (3, 224, 224)


def test_metrics_and_temperature() -> None:
    rng = np.random.default_rng(0)
    y = rng.integers(0, 4, 2000)
    logits = rng.normal(size=(2000, 4))
    logits[np.arange(2000), y] += 2.0
    over = logits * 4  # overconfident copy
    t, t_base = M.fit_temperature(over, y), M.fit_temperature(logits, y)
    assert abs(t / t_base - 4) < 0.1  # scaling logits by 4 must scale the optimum by 4
    assert M.ece(M.softmax(over, t), y) < M.ece(M.softmax(over), y)
    r = M.classification(logits, y, list("abcd"))
    assert 0 <= r["macro_f1"] <= 1 and len(r["confusion_matrix"]) == 4
    perfect = np.eye(4)[y] * 10
    assert M.classification(perfect, y, list("abcd"))["accuracy"] == 1.0


def _fixture(tmp: Path) -> dict:
    cache = tmp / "cache"
    cache.mkdir()
    rows = []
    for i in range(48):
        cls = ["healthy", "late_blight"][i % 2]
        col = (30, 170, 40) if cls == "healthy" else (120, 80, 30)
        Image.new("RGB", (256, 256), col).save(cache / f"id{i}.jpg")
        rows.append(
            {
                "image_id": f"id{i}",
                "class": cls,
                "source": "s",
                "split": "train" if i < 32 else "val",
            }
        )
    with (tmp / "split.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (tmp / "cm.json").write_text(json.dumps({"classes": ["healthy", "late_blight"]}))
    return {
        "exp_id": "t",
        "arch": "small_cnn",
        "pretrained": False,
        "class_map": str(tmp / "cm.json"),
        "split": str(tmp / "split.csv"),
        "cache": str(cache),
        "runs_root": str(tmp / "runs"),
        "img_size": 64,
        "batch_size": 8,
        "epochs": 2,
        "lr": 1e-3,
        "seed": 1,
        "num_workers": 0,
        "val_num_workers": 0,
        "patience": 5,
    }


def test_training_sanity_checkpoint_and_resume(tmp_path: Path) -> None:
    cfg = _fixture(tmp_path)
    s = run(cfg, allow_cpu=True)
    rd = Path(s["run_dir"])
    assert (rd / "best.pt").exists() and (rd / "last.pt").exists()
    hist = json.loads((rd / "history.json").read_text())
    assert len(hist) == 2 and all(np.isfinite(h["train_loss"]) for h in hist)
    best = torch.load(rd / "best.pt", weights_only=True)  # safe loading (no pickle code)
    assert best["classes"] == ["healthy", "late_blight"]
    assert best["val_macro_f1"] == max(h["val_macro_f1"] for h in hist)
    s2 = run({**cfg, "epochs": 3}, allow_cpu=True)  # resumes at epoch 2
    assert s2["epochs_run"] == 3
    assert torch.load(rd / "best.pt", weights_only=True)["val_macro_f1"] >= best["val_macro_f1"]


def test_worker_memory_guard_refuses_unsafe_worker_count() -> None:
    # 16 workers on the 2026-11-23 hang state (6.9 GB RAM, 16.6 GB commit free) must refuse.
    with pytest.raises(SystemExit, match="Refusing to start"):
        check_worker_memory(16, status=(6.9, 16.6))
    check_worker_memory(2, status=(5.0, 16.6))  # 2 workers (committed configs): allowed
    with pytest.raises(SystemExit):  # 4 workers at 5.3 GB free: killed by watchdog 2026-11-23
        check_worker_memory(4, status=(5.3, 14.2))
    check_worker_memory(0, status=(0.5, 0.5))  # in-process loading spawns nothing
