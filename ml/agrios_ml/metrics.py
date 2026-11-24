"""Classification + calibration metrics computed from saved logits (no model needed)."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
    top_k_accuracy_score,
)


def softmax(z: np.ndarray, t: float = 1.0) -> np.ndarray:
    z = z / t
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def ece(probs: np.ndarray, y: np.ndarray, bins: int = 15) -> float:
    conf, pred = probs.max(1), probs.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs((pred[m] == y[m]).mean() - conf[m].mean())
    return float(total)


def reliability(probs: np.ndarray, y: np.ndarray, bins: int = 15) -> list[dict[str, float]]:
    conf, pred = probs.max(1), probs.argmax(1)
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:], strict=True):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            out.append(
                {
                    "lo": float(lo),
                    "hi": float(hi),
                    "n": int(m.sum()),
                    "conf": float(conf[m].mean()),
                    "acc": float((pred[m] == y[m]).mean()),
                }
            )
    return out


def brier(probs: np.ndarray, y: np.ndarray) -> float:
    onehot = np.eye(probs.shape[1])[y]
    return float(((probs - onehot) ** 2).sum(1).mean())


def nll(probs: np.ndarray, y: np.ndarray) -> float:
    return float(-np.log(np.clip(probs[np.arange(len(y)), y], 1e-12, 1)).mean())


def fit_temperature(logits: np.ndarray, y: np.ndarray) -> float:
    """Temperature scaling (Guo et al., 2017): 1-D NLL minimisation on VALIDATION logits."""
    grid = np.exp(np.linspace(np.log(0.05), np.log(20), 400))
    losses = [nll(softmax(logits, t), y) for t in grid]
    t0 = float(grid[int(np.argmin(losses))])
    fine = np.linspace(t0 * 0.9, t0 * 1.1, 200)
    return float(fine[int(np.argmin([nll(softmax(logits, t), y) for t in fine]))])


def classification(
    logits: np.ndarray, y: np.ndarray, classes: list[str], temperature: float = 1.0
) -> dict[str, Any]:
    k = len(classes)
    probs = softmax(logits, temperature)
    pred = probs.argmax(1)
    labels = list(range(k))
    p, r, f, s = precision_recall_fscore_support(y, pred, labels=labels, zero_division=0)
    present = s > 0
    return {
        "n": int(len(y)),
        "accuracy": float(accuracy_score(y, pred)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)) if len(y) else None,
        "macro_precision": float(p[present].mean()) if present.any() else None,
        "macro_recall": float(r[present].mean()) if present.any() else None,
        "macro_f1": float(f[present].mean()) if present.any() else None,
        "macro_f1_note": "averaged over classes present in this split",
        "weighted_f1": float(f1_score(y, pred, labels=labels, average="weighted", zero_division=0)),
        "top3_accuracy": float(top_k_accuracy_score(y, probs, k=3, labels=labels))
        if k > 3
        else None,
        "ece_15": ece(probs, y),
        "brier": brier(probs, y),
        "nll": nll(probs, y),
        "temperature": temperature,
        "per_class": {
            classes[i]: {
                "precision": float(p[i]),
                "recall": float(r[i]),
                "f1": float(f[i]),
                "support": int(s[i]),
            }
            for i in labels
        },
        "confusion_matrix": confusion_matrix(y, pred, labels=labels).tolist(),
        "reliability": reliability(probs, y),
    }


def selective_risk(
    probs: np.ndarray,
    y: np.ndarray,
    thresholds: tuple[float, ...] = (0.5, 0.6, 0.7, 0.8, 0.9, 0.95),
) -> list[dict[str, float]]:
    conf, pred = probs.max(1), probs.argmax(1)
    out = []
    for t in thresholds:
        m = conf >= t
        out.append(
            {
                "threshold": t,
                "coverage": float(m.mean()),
                "accuracy_accepted": float((pred[m] == y[m]).mean()) if m.any() else None,
            }
        )
    return out
