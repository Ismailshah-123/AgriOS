"""Evaluate a trained run. Validation always; test + external ONLY with --final (after model
selection is complete). Temperature and abstention threshold are fitted on VALIDATION.

python -m agrios_ml.evaluate <run_dir> --report-dir reports/<exp>/<run> [--final]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from agrios_ml import metrics as M  # noqa: E402
from agrios_ml.data.dataset import SplitDataset, eval_transform, read_split  # noqa: E402
from agrios_ml.nets import build_model, count_params  # noqa: E402
from agrios_ml.train import predict, resolve  # noqa: E402


def plot_cm(cm: list[list[int]], classes: list[str], title: str, path: Path) -> None:
    a = np.array(cm, dtype=float)
    norm = a / np.maximum(a.sum(1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(8, 7))
    ax.imshow(norm, cmap="Greens", vmin=0, vmax=1)
    ax.set_xticks(range(len(classes)), classes, rotation=60, ha="right", fontsize=8)
    ax.set_yticks(range(len(classes)), classes, fontsize=8)
    for i in range(len(classes)):
        for j in range(len(classes)):
            if a[i, j]:
                ax.text(
                    j,
                    i,
                    int(a[i, j]),
                    ha="center",
                    va="center",
                    fontsize=7,
                    color="white" if norm[i, j] > 0.5 else "black",
                )
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_reliability(before: list[dict], after: list[dict], path: Path) -> None:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=1)
    for rel, lab in ((before, "T=1"), (after, "calibrated")):
        ax.plot([r["conf"] for r in rel], [r["acc"] for r in rel], "o-", label=lab)
    ax.set_xlabel("Confidence")
    ax.set_ylabel("Accuracy")
    ax.legend()
    ax.set_title("Reliability (validation)")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_history(hist: list[dict], path: Path) -> None:
    ep = [h["epoch"] for h in hist]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    a1.plot(ep, [h["train_loss"] for h in hist], label="train loss (weighted CE)")
    a1.plot(ep, [h["val_loss"] for h in hist], label="val loss (CE)")
    a1.legend()
    a1.set_xlabel("epoch")
    a2.plot(ep, [h["train_acc"] for h in hist], label="train acc")
    a2.plot(ep, [h["val_acc"] for h in hist], label="val acc")
    a2.plot(ep, [h["val_macro_f1"] for h in hist], label="val macro-F1")
    a2.legend()
    a2.set_xlabel("epoch")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def latency(model: torch.nn.Module, device: torch.device, n: int = 50) -> dict[str, float]:
    x = torch.randn(1, 3, 224, 224, device=device)
    model.eval()
    with torch.no_grad():
        for _ in range(10):
            model(x)
        if device.type == "cuda":
            torch.cuda.synchronize()
        ts = []
        for _ in range(n):
            t0 = time.perf_counter()
            model(x)
            if device.type == "cuda":
                torch.cuda.synchronize()
            ts.append((time.perf_counter() - t0) * 1000)
    return {"p50_ms": float(np.percentile(ts, 50)), "p95_ms": float(np.percentile(ts, 95))}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--report-dir", type=Path, required=True)
    ap.add_argument("--final", action="store_true", help="also evaluate test + external")
    a = ap.parse_args()
    cfg = json.loads((a.run_dir / "config.json").read_text(encoding="utf-8"))
    classes = json.loads(resolve(cfg["class_map"]).read_text(encoding="utf-8"))["classes"]
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(a.run_dir / "best.pt", map_location=device, weights_only=True)
    model = build_model(cfg["arch"], len(classes), pretrained=False)
    model.load_state_dict(ck["model"])
    model.to(device).eval()
    split, cache = resolve(cfg["split"]), resolve(cfg["cache"])
    out = a.report_dir
    out.mkdir(parents=True, exist_ok=True)

    def logits_for(name: str) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        rows = read_split(split, classes, name)
        ds = SplitDataset(rows, classes, cache, eval_transform(cfg.get("img_size", 224)))
        dl = DataLoader(ds, 128, num_workers=cfg.get("num_workers", 6), pin_memory=True)
        lg, y = predict(model, dl, device, amp=device.type == "cuda")
        return lg, y, rows

    vl, vy, _ = logits_for("val")
    t = M.fit_temperature(vl, vy)
    res = {
        "exp_id": cfg["exp_id"],
        "arch": cfg["arch"],
        "best_epoch": ck["epoch"],
        "temperature": t,
        "classes": classes,
        "val": M.classification(vl, vy, classes, 1.0),
        "val_calibrated": M.classification(vl, vy, classes, t),
        "val_selective": M.selective_risk(M.softmax(vl, t), vy),
    }
    plot_reliability(
        res["val"]["reliability"], res["val_calibrated"]["reliability"], out / "reliability_val.png"
    )
    plot_cm(
        res["val"]["confusion_matrix"],
        classes,
        f"{cfg['exp_id']} validation",
        out / "confusion_val.png",
    )
    hist = json.loads((a.run_dir / "history.json").read_text(encoding="utf-8"))
    plot_history(hist, out / "curves.png")
    if a.final:
        for name in ("test", "external_test"):
            lg, y, rows = logits_for(name)
            np.save(a.run_dir / f"{name}_logits.npy", lg)
            r = M.classification(lg, y, classes, t)
            r["selective"] = M.selective_risk(M.softmax(lg, t), y)
            by_src: dict[str, list[int]] = defaultdict(list)
            for i, row in enumerate(rows):
                by_src[row["source"]].append(i)
            r["per_source"] = {
                s: {
                    k: v
                    for k, v in M.classification(lg[ix], y[ix], classes, t).items()
                    if k in ("n", "accuracy", "macro_f1")
                }
                for s, ix in by_src.items()
            }
            res[name] = r
            plot_cm(
                r["confusion_matrix"],
                classes,
                f"{cfg['exp_id']} {name}",
                out / f"confusion_{name}.png",
            )
    size = (a.run_dir / "best.pt").stat().st_size
    res["model"] = {
        "params": count_params(model),
        "checkpoint_bytes": size,
        "latency_gpu_bs1": latency(model, device) if device.type == "cuda" else None,
        "latency_cpu_bs1": latency(model.cpu(), torch.device("cpu"), 20),
    }
    res["final_evaluation"] = a.final
    (out / "metrics.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    (out / "history.json").write_text(json.dumps(hist, indent=2), encoding="utf-8")
    keep = {k: res[k] for k in ("exp_id", "temperature")}
    for k in ("val", "val_calibrated", "test", "external_test"):
        if k in res:
            keep[k] = {
                m: res[k][m]
                for m in ("n", "accuracy", "macro_f1", "weighted_f1", "ece_15", "brier")
            }
    print(json.dumps(keep, indent=2))


if __name__ == "__main__":
    main()
