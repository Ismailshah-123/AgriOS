"""Out-of-scope (unsupported crop) rejection evaluation.

Unknown set = a seeded sample of NON-tomato images from agri_foundation_v1 (other crops the
model never saw: genuinely held-out categories). In-distribution = tomato TEST split.
Reports energy-score AUROC and the rejection rates at the packaged thresholds. This tests
"other crop leaves" only; arbitrary non-plant photos are NOT covered by this evaluation.

python -m agrios_ml.ood <run_dir> --package <pkg_dir> --manifest <dataset_manifest.csv>
       --raw-root <root> --cache <cache_dir> --out <report_dir> [--n 3000]
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader

from agrios_ml import metrics as M
from agrios_ml.data import cache as cache_mod
from agrios_ml.data.dataset import SplitDataset, eval_transform, read_split
from agrios_ml.nets import build_model
from agrios_ml.package import energy
from agrios_ml.train import predict, resolve


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--package", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--raw-root", type=Path, required=True)
    ap.add_argument("--cache", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n", type=int, default=3000)
    ap.add_argument("--seed", type=int, default=7)
    # Each Windows spawn worker re-imports this module (and torch): ~0.7 GB RAM + 1.7 GB commit
    # per worker on the 15.6 GB dev PC. 8 workers is the configuration that hung it; keep 2.
    ap.add_argument("--workers", type=int, default=2)
    a = ap.parse_args()
    pkg = json.loads((a.package / "package.json").read_text(encoding="utf-8"))
    cfg = json.loads((a.run_dir / "config.json").read_text(encoding="utf-8"))
    classes = [lbl["label"] for lbl in pkg["labels"]]

    with a.manifest.open(encoding="utf-8", newline="") as fh:
        other = [
            r for r in csv.DictReader(fh) if r["crop"] != "tomato" and r["decode_ok"] == "True"
        ]
    rng = random.Random(a.seed)  # noqa: S311 (reproducible sampling, not crypto)
    sample = rng.sample(other, min(a.n, len(other)))
    a.out.mkdir(parents=True, exist_ok=True)
    ood_csv = a.out / "ood_sample.csv"
    with ood_csv.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(
            fh, fieldnames=["image_id", "release_path", "crop", "source", "split", "class"]
        )
        w.writeheader()
        for r in sample:
            w.writerow(
                {
                    "image_id": r["image_id"],
                    "release_path": r["release_path"],
                    "crop": r["crop"],
                    "source": r["source"],
                    "split": "ood",
                    "class": classes[0],
                }
            )
    cache_mod.build(ood_csv, a.raw_root, a.cache, 256, a.workers)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(a.run_dir / "best.pt", map_location=device, weights_only=True)
    model = build_model(cfg["arch"], len(classes), pretrained=False)
    model.load_state_dict(ck["model"])
    model.to(device).eval()

    def logits(rows: list[dict], cache: Path) -> np.ndarray:
        ds = SplitDataset(rows, classes, cache, eval_transform())
        return predict(model, DataLoader(ds, 128, num_workers=6), device, device.type == "cuda")[0]

    t = pkg["temperature"]
    ind = logits(read_split(resolve(cfg["split"]), classes, "test"), resolve(cfg["cache"]))
    ood_rows = list(csv.DictReader(ood_csv.open(encoding="utf-8")))
    ood = logits(ood_rows, a.cache)
    e_in, e_out = energy(ind, t), energy(ood, t)
    auroc = float(
        roc_auc_score(np.r_[np.zeros(len(e_in)), np.ones(len(e_out))], np.r_[e_in, e_out])
    )
    p_out = M.softmax(ood, t).max(1)
    rejected_energy = e_out > pkg["ood_threshold"]
    not_accepted = rejected_energy | (p_out < pkg["threshold"])
    by_crop: dict[str, list[bool]] = {}
    for r, rej in zip(ood_rows, not_accepted, strict=True):
        by_crop.setdefault(r["crop"], []).append(bool(rej))
    res = {
        "unknown_set": (
            f"{len(ood)} non-tomato images (seed {a.seed}), crops never seen in training"
        ),
        "in_distribution": f"{len(ind)} tomato test images",
        "energy_auroc": auroc,
        "ood_threshold": pkg["ood_threshold"],
        "conf_threshold": pkg["threshold"],
        "in_dist_flagged_out_of_scope_rate": float((e_in > pkg["ood_threshold"]).mean()),
        "unknown_flagged_out_of_scope_rate": float(rejected_energy.mean()),
        "unknown_not_accepted_rate": float(not_accepted.mean()),
        "unknown_not_accepted_by_crop": {
            k: round(float(np.mean(v)), 4) for k, v in sorted(by_crop.items())
        },
        "limitation": (
            "Only other-crop leaf images were tested; non-plant images are not evaluated."
        ),
    }
    (a.out / "ood_metrics.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
