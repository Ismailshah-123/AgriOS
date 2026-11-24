"""Model-independent inference contract (MODULE_CONTRACTS section 2).

A Predictor only maps images to raw class scores. Calibration (temperature), the
out-of-distribution score and the accept / unsure / out-of-scope decision are applied by
`decide()` using the immutable model_versions row, so a model can never declare itself
confident. Output is validated before anything is stored.
"""

import math
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ModelInput:
    images: list[bytes]  # processed WebP derivatives (EXIF-free)
    crop_code: str


@dataclass(frozen=True)
class RawOutput:
    logits: list[float]  # one per model label, in registry order; aggregated over images
    explanation: dict[str, Any] | None = None  # e.g. {"gradcam_keys": [...]}; optional
    extra: dict[str, Any] = field(default_factory=dict)


class Predictor(Protocol):
    def predict(self, x: ModelInput) -> RawOutput: ...


class InvalidModelOutput(ValueError):
    pass


@dataclass(frozen=True)
class Decision:
    decision: str  # "accepted" | "unsure" | "out_of_scope"
    predicted_class: str | None
    calibrated_conf: float
    ood_score: float
    probs: dict[str, float]
    shortlist: list[dict[str, float | str]]


def _softmax(z: list[float]) -> list[float]:
    m = max(z)
    e = [math.exp(v - m) for v in z]
    s = sum(e)
    return [v / s for v in e]


def decide(
    raw: RawOutput,
    labels: list[str],
    temperature: float | None,
    threshold: float | None,
    ood_threshold: float | None,
) -> Decision:
    """Validate model output and apply the documented decision rule."""
    z = raw.logits
    if len(z) != len(labels) or not labels:
        raise InvalidModelOutput("logit count does not match registered labels")
    if not all(isinstance(v, int | float) and math.isfinite(v) for v in z):
        raise InvalidModelOutput("non-finite logits")
    if threshold is None or ood_threshold is None:
        # An uncalibrated model may run, but it must never produce an accepted result.
        threshold, ood_threshold = 1.01, float("inf")
    t = temperature if temperature and temperature > 0 else 1.0
    scaled = [v / t for v in z]
    probs = _softmax(scaled)
    m = max(scaled)
    energy = -(m + math.log(sum(math.exp(v - m) for v in scaled)))  # lower = in-distribution
    top = sorted(range(len(probs)), key=probs.__getitem__, reverse=True)
    best = top[0]
    conf = probs[best]
    if energy > ood_threshold:
        decision, cls = "out_of_scope", None
    elif conf >= threshold:
        decision, cls = "accepted", labels[best]
    else:
        decision, cls = "unsure", None
    return Decision(
        decision=decision,
        predicted_class=cls,
        calibrated_conf=round(conf, 5),
        ood_score=round(energy, 4),
        probs={labels[i]: round(p, 6) for i, p in enumerate(probs)},
        shortlist=[{"label": labels[i], "probability": round(probs[i], 4)} for i in top[:3]],
    )
