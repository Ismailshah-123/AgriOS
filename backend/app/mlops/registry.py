"""Model availability (system-level, MODULE_CONTRACTS section 2) and predictor loading.

Availability is decided from facts, never assumed:
  not_registered     no ACTIVE model_versions row for the task
  not_installed      active row, but the artefact file is missing under MODEL_PATH
  checksum_mismatch  artefact present but its SHA-256 differs from the registry
  error              artefact verified but no runtime/loader exists for its framework
  ready              artefact verified and a loader is available
Phase 4: an ONNX Runtime loader (framework "onnx") serves exported PyTorch models on CPU.
"""

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.mlops.models import ModelStatus, ModelVersion
from app.mlops.predictor import Predictor

CROP_HEALTH_TASK = "crop_health_image"

# framework -> loader(model_version, artefact_path) -> Predictor.
LOADERS: dict[str, Callable[[ModelVersion, Path], Predictor]] = {}
try:  # ONNX Runtime serving (CPU). Absent runtime => availability "error: no runtime".
    import onnxruntime  # noqa: F401

    from app.mlops import onnx_predictor

    LOADERS["onnx"] = onnx_predictor.load
except ImportError:  # pragma: no cover - depends on installed extras
    pass


@dataclass(frozen=True)
class Availability:
    status: str
    reason: str
    model: ModelVersion | None = None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def active_model(db: Session, task: str) -> ModelVersion | None:
    return db.scalar(
        select(ModelVersion).where(
            ModelVersion.task == task, ModelVersion.status == ModelStatus.ACTIVE
        )
    )


def availability(db: Session, model_root: Path, task: str = CROP_HEALTH_TASK) -> Availability:
    model = active_model(db, task)
    if model is None:
        return Availability("not_registered", "No evaluated model has been activated.")
    root = model_root.resolve()
    path = (root / model.artifact_uri).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return Availability("not_installed", "The model file is not installed.", model)
    if _sha256(path) != model.checksum_sha256:
        return Availability("checksum_mismatch", "The model file failed verification.", model)
    if model.framework not in LOADERS:
        return Availability("error", f"No runtime for framework '{model.framework}'.", model)
    return Availability("ready", "Model verified.", model)


def load_predictor(model: ModelVersion, model_root: Path) -> Predictor:
    return LOADERS[model.framework](model, (model_root / model.artifact_uri).resolve())
