"""Config-driven training (CUDA required unless --allow-cpu for tiny smoke tests).

python -m agrios_ml.train experiments/configs/<cfg>.json [--max-batches N] [--allow-cpu]

Run dir = <runs_root>/<exp_id>/seed<seed>/ : last.pt (every epoch, for resume), best.pt
(only replaced when val macro-F1 strictly improves), history.json, val_logits.npy,
config.json. The TEST split is never touched here (model selection uses validation only).
Checkpoints contain only tensors + plain metadata, loadable with weights_only=True.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.metrics import f1_score
from torch import nn
from torch.utils.data import DataLoader

from agrios_ml.data.dataset import SplitDataset, eval_transform, read_split, train_transform
from agrios_ml.nets import build_model, count_params, head_parameters

ML_DIR = Path(__file__).resolve().parents[1]


def seed_all(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def class_weights(targets: list[int], k: int, mode: str) -> torch.Tensor:
    counts = np.bincount(targets, minlength=k).astype(np.float64)
    if mode == "none":
        w = np.ones(k)
    elif mode == "inverse_sqrt":
        w = 1.0 / np.sqrt(np.maximum(counts, 1))
    else:
        w = 1.0 / np.maximum(counts, 1)
    return torch.tensor(w * k / w.sum(), dtype=torch.float32)  # mean weight = 1


def lr_lambda(total_steps: int, warmup: int):  # noqa: ANN201
    def f(step: int) -> float:
        if step < warmup:
            return (step + 1) / warmup
        p = (step - warmup) / max(1, total_steps - warmup)
        return 0.5 * (1 + math.cos(math.pi * min(1.0, p)))

    return f


@torch.no_grad()
def predict(
    model: nn.Module,
    loader: DataLoader,
    device: torch.device,
    amp: bool,
    max_batches: int | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    model.eval()
    out, ys = [], []
    for b, (x, y) in enumerate(loader):
        if max_batches and b >= max_batches:
            break
        with torch.autocast(device.type, dtype=torch.float16, enabled=amp):
            out.append(model(x.to(device, non_blocking=True)).float().cpu())
        ys.append(y)
    return torch.cat(out).numpy(), torch.cat(ys).numpy()


# Windows spawns each DataLoader worker as a fresh process that re-imports torch (CUDA DLLs):
# measured 2026-11-23 on the RTX 3060 box = ~0.65 GB RAM + ~1.73 GB commit per worker.
# 16 workers exhausted RAM/commit and hung the PC (unclean reboot), so refuse unsafe configs.
# Main process (resident when checked) still grows ~1-2 GB once training starts: 3 GB headroom.
WORKER_RAM_GB, WORKER_COMMIT_GB, HEADROOM_GB = 0.7, 1.8, 3.0


def memory_status_gb() -> tuple[float, float] | None:
    """(available physical RAM, available commit) in GB; None where unsupported."""
    if os.name != "nt":
        return None
    import ctypes

    class MemStat(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    s = MemStat()
    s.dwLength = ctypes.sizeof(MemStat)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(s)):
        return None
    return s.ullAvailPhys / 2**30, s.ullAvailPageFile / 2**30


def check_worker_memory(workers: int, status: tuple[float, float] | None = None) -> None:
    status = status if status is not None else memory_status_gb()
    if status is None or workers == 0:
        return
    ram, commit = status
    need_ram = HEADROOM_GB + workers * WORKER_RAM_GB
    need_commit = HEADROOM_GB + workers * WORKER_COMMIT_GB
    if ram < need_ram or commit < need_commit:
        raise SystemExit(
            f"Refusing to start: {workers} DataLoader workers need ~{need_ram:.1f} GB RAM and "
            f"~{need_commit:.1f} GB commit; available {ram:.1f} GB RAM, {commit:.1f} GB commit. "
            "Lower num_workers/val_num_workers or close other applications."
        )


def _worker_init(_: int) -> None:
    # One intra-op thread per worker: 6 threads x N workers oversubscribed the CPU
    # (train transform 7.2 -> 2.8 ms/img, measured 2026-11-23).
    torch.set_num_threads(1)


def resolve(p: str) -> Path:
    q = Path(p)
    return q if q.is_absolute() else (ML_DIR / q).resolve()


def run(cfg: dict[str, Any], max_batches: int | None = None, allow_cpu: bool = False) -> dict:
    if not torch.cuda.is_available() and not allow_cpu:
        raise SystemExit("CUDA not available: refusing to start a GPU training run on CPU.")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    amp = bool(cfg.get("amp", True)) and device.type == "cuda"
    seed_all(cfg["seed"])
    torch.backends.cudnn.benchmark = True  # speed over bitwise determinism (documented)
    cmap = json.loads(resolve(cfg["class_map"]).read_text(encoding="utf-8"))
    classes = cmap["classes"]
    split, cache = resolve(cfg["split"]), resolve(cfg["cache"])
    size = cfg.get("img_size", 224)
    tr = SplitDataset(
        read_split(split, classes, "train"),
        classes,
        cache,
        train_transform(size, cfg.get("augment", "medium")),
    )
    va = SplitDataset(read_split(split, classes, "val"), classes, cache, eval_transform(size))
    nw, vnw = cfg.get("num_workers", 4), cfg.get("val_num_workers", 2)
    check_worker_memory(nw + vnw)

    def loader_kw(n: int) -> dict[str, Any]:
        return {
            "num_workers": n,
            "pin_memory": device.type == "cuda",
            "persistent_workers": n > 0,
            "prefetch_factor": cfg.get("prefetch_factor", 2) if n > 0 else None,
            "worker_init_fn": _worker_init if n > 0 else None,
        }

    g = torch.Generator().manual_seed(cfg["seed"])
    tl = DataLoader(
        tr, cfg["batch_size"], shuffle=True, drop_last=True, generator=g, **loader_kw(nw)
    )
    vl = DataLoader(va, cfg["batch_size"] * 2, shuffle=False, **loader_kw(vnw))

    model = build_model(cfg["arch"], len(classes), cfg.get("pretrained", True)).to(device)
    model = model.to(memory_format=torch.channels_last)
    weights = class_weights(tr.targets, len(classes), cfg.get("class_weighting", "inverse_sqrt"))
    crit = nn.CrossEntropyLoss(
        weight=weights.to(device), label_smoothing=cfg.get("label_smoothing", 0.0)
    )
    head_ep = cfg.get("head_epochs", 0) if cfg["arch"] != "small_cnn" else 0
    epochs = cfg["epochs"]
    steps_per_epoch = min(len(tl), max_batches or len(tl))

    def make_opt(params: list, lr: float) -> torch.optim.Optimizer:
        return torch.optim.AdamW(params, lr=lr, weight_decay=cfg.get("weight_decay", 1e-4))

    run_dir = resolve(cfg.get("runs_root", "runs")) / cfg["exp_id"] / f"seed{cfg['seed']}"
    if max_batches:
        run_dir = run_dir.with_name(run_dir.name + "_smoke")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    hist: list[dict[str, Any]] = []
    best_f1, bad_epochs, start_ep = -1.0, 0, 0
    scaler = torch.amp.GradScaler("cuda", enabled=amp)

    def stage(ep: int) -> tuple[torch.optim.Optimizer, torch.optim.lr_scheduler.LambdaLR]:
        frozen = ep < head_ep
        for p in model.parameters():
            p.requires_grad = not frozen
        for p in head_parameters(model, cfg["arch"]):
            p.requires_grad = True
        if frozen:
            opt = make_opt(head_parameters(model, cfg["arch"]), cfg.get("head_lr", 3e-3))
            sch = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: 1.0)
        else:
            opt = make_opt([p for p in model.parameters() if p.requires_grad], cfg["lr"])
            total = (epochs - head_ep) * steps_per_epoch
            sch = torch.optim.lr_scheduler.LambdaLR(
                opt, lr_lambda(total, cfg.get("warmup_epochs", 1) * steps_per_epoch)
            )
        return opt, sch

    last = run_dir / "last.pt"
    opt, sch = stage(0)
    if last.exists():  # resume
        ck = torch.load(last, map_location=device, weights_only=True)
        start_ep = ck["epoch"] + 1
        model.load_state_dict(ck["model"])
        opt, sch = stage(start_ep)
        if (start_ep - 1 < head_ep) == (start_ep < head_ep):  # same stage: restore optimizer
            opt.load_state_dict(ck["opt"])
            sch.load_state_dict(ck["sched"])
        scaler.load_state_dict(ck["scaler"])
        best_f1, bad_epochs = ck["best_f1"], ck["bad_epochs"]
        hist = json.loads((run_dir / "history.json").read_text(encoding="utf-8"))
        print(f"resumed at epoch {start_ep} best_f1={best_f1:.4f}", flush=True)

    t_run = time.time()
    for ep in range(start_ep, epochs):
        if ep == head_ep and ep > 0 and ep != start_ep:  # head-only -> full fine-tuning
            opt, sch = stage(ep)
        model.train()
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        t0, loss_sum, seen, correct = time.time(), 0.0, 0, 0
        for b, (x, y) in enumerate(tl):
            if b >= steps_per_epoch:
                break
            x = x.to(device, non_blocking=True).to(memory_format=torch.channels_last)
            y = y.to(device, non_blocking=True)
            with torch.autocast(device.type, dtype=torch.float16, enabled=amp):
                logits = model(x)
                loss = crit(logits, y)
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            nn.utils.clip_grad_norm_(model.parameters(), cfg.get("grad_clip", 1.0))
            scaler.step(opt)
            scaler.update()
            sch.step()
            loss_sum += loss.item() * len(y)
            seen += len(y)
            correct += (logits.argmax(1) == y).sum().item()
        train_s = time.time() - t0
        vlog, vy = predict(model, vl, device, amp, max_batches)
        vloss = float(nn.functional.cross_entropy(torch.from_numpy(vlog), torch.from_numpy(vy)))
        vf1 = float(f1_score(vy, vlog.argmax(1), average="macro"))
        rec = {
            "epoch": ep,
            "stage": "head" if ep < head_ep else "full",
            "train_loss": loss_sum / max(seen, 1),
            "train_acc": correct / max(seen, 1),
            "val_loss": vloss,
            "val_acc": float((vlog.argmax(1) == vy).mean()),
            "val_macro_f1": vf1,
            "lr": opt.param_groups[0]["lr"],
            "epoch_seconds": round(time.time() - t0, 1),
            "train_seconds": round(train_s, 1),
            "images_per_s": round(seen / max(train_s, 1e-9), 1),
            "peak_gpu_mem_mb": round(torch.cuda.max_memory_allocated() / 2**20)
            if torch.cuda.is_available()
            else None,
        }
        improved = vf1 > best_f1
        if improved:
            best_f1, bad_epochs = vf1, 0
            torch.save(
                {
                    "model": model.state_dict(),
                    "epoch": ep,
                    "val_macro_f1": vf1,
                    "arch": cfg["arch"],
                    "classes": classes,
                },
                run_dir / "best.pt.tmp",
            )
            (run_dir / "best.pt.tmp").replace(run_dir / "best.pt")
            np.save(run_dir / "val_logits.npy", vlog)
            np.save(run_dir / "val_targets.npy", vy)
        else:
            bad_epochs += 1
        rec["best"] = improved
        hist.append(rec)
        (run_dir / "history.json").write_text(json.dumps(hist, indent=2), encoding="utf-8")
        torch.save(
            {
                "model": model.state_dict(),
                "opt": opt.state_dict(),
                "sched": sch.state_dict(),
                "scaler": scaler.state_dict(),
                "epoch": ep,
                "best_f1": best_f1,
                "bad_epochs": bad_epochs,
            },
            run_dir / "last.pt.tmp",
        )
        (run_dir / "last.pt.tmp").replace(last)
        print(json.dumps(rec), flush=True)
        if ep >= head_ep and bad_epochs >= cfg.get("patience", 4):
            print(f"early stop at epoch {ep}", flush=True)
            break
    summary = {
        "exp_id": cfg["exp_id"],
        "arch": cfg["arch"],
        "params": count_params(model),
        "train_images": len(tr),
        "val_images": len(va),
        "best_val_macro_f1": best_f1,
        "epochs_run": len(hist),
        "run_dir": str(run_dir),
        "wall_seconds_this_session": round(time.time() - t_run, 1),
        "device": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu",
        "torch": torch.__version__,
        "class_weights": weights.tolist(),
    }
    (run_dir / "train_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("config", type=Path)
    ap.add_argument("--max-batches", type=int, default=None)
    ap.add_argument("--allow-cpu", action="store_true")
    a = ap.parse_args()
    cfg = json.loads(a.config.read_text(encoding="utf-8"))
    print(json.dumps(run(cfg, a.max_batches, a.allow_cpu), indent=2))


if __name__ == "__main__":
    main()
