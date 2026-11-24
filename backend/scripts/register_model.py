"""Admin CLI: install + register a packaged model version (and optionally activate it).

uv run python scripts/register_model.py <package_dir> [--activate] [--notes "..."]

- Verifies the ONNX checksum against package.json before copying.
- Copies the package to MODEL_PATH/<name>/<version>/ (refuses to overwrite).
- Inserts a model_versions row (status candidate). --activate retires the current active
  model for the task and activates this one. Both steps write audit events.
Uses DATABASE_URL from backend/.env (never prints it).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select, update  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.audit import service as audit  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db import models_registry  # noqa: E402, F401 - complete metadata for FKs (audit -> users)
from app.mlops.models import ModelStatus, ModelVersion  # noqa: E402

ALLOWED = {"model.onnx", "cam_weights.npy", "package.json"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for b in iter(lambda: fh.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def install(pkg_dir: Path, model_root: Path) -> tuple[dict, str]:
    pkg = json.loads((pkg_dir / "package.json").read_text(encoding="utf-8"))
    if sha256(pkg_dir / pkg["artifact"]) != pkg["checksum_sha256"]:
        raise SystemExit("checksum mismatch: package is corrupt")
    rel = f"{pkg['name']}/{pkg['version']}"
    dest = model_root / rel
    if dest.exists():
        raise SystemExit(f"{rel} already installed (versions are immutable)")
    dest.mkdir(parents=True)
    for f in pkg_dir.iterdir():
        if f.is_file() and f.name in ALLOWED:
            shutil.copy2(f, dest / f.name)
    return pkg, f"{rel}/{pkg['artifact']}"


def register(db: Session, pkg: dict, uri: str, activate: bool, notes: str | None) -> ModelVersion:
    mv = ModelVersion(
        task=pkg["task"],
        name=pkg["name"],
        version=pkg["version"],
        framework=pkg["framework"],
        arch=pkg["arch"],
        labels=pkg["labels"],
        supported_crops=pkg["supported_crops"],
        artifact_uri=uri,
        checksum_sha256=pkg["checksum_sha256"],
        data_hash=pkg["split_sha256"],
        config={
            "preprocessing": pkg["preprocessing"],
            "cam_weights_file": pkg["cam_weights_file"],
            "threshold_policy": pkg["threshold_policy"],
            "metrics_summary": pkg["metrics_summary"],
        },
        metrics_ref=f"ml/reports/{pkg['train_config']['exp_id']}",
        model_card_uri="ml/reports/MODEL_CARD.md",
        temperature=pkg["temperature"],
        threshold=pkg["threshold"],
        ood_threshold=pkg["ood_threshold"],
        status=ModelStatus.CANDIDATE,
        notes=notes,
    )
    db.add(mv)
    db.flush()
    audit.record(
        db,
        action="model_version.registered",
        entity="model_version",
        entity_id=mv.id,
        meta={"name": mv.name, "version": mv.version},
    )
    if activate:
        db.execute(
            update(ModelVersion)
            .where(ModelVersion.task == mv.task, ModelVersion.status == ModelStatus.ACTIVE)
            .values(status=ModelStatus.RETIRED)
        )
        db.flush()
        mv.status = ModelStatus.ACTIVE
        audit.record(
            db,
            action="model_version.activated",
            entity="model_version",
            entity_id=mv.id,
            meta={"name": mv.name, "version": mv.version},
        )
    db.commit()
    return mv


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("package_dir", type=Path)
    ap.add_argument("--activate", action="store_true")
    ap.add_argument("--notes")
    a = ap.parse_args()
    s = get_settings()
    if s.database_url is None:
        raise SystemExit("DATABASE_URL not configured")
    pkg, uri = install(a.package_dir, s.model_path)
    engine = create_engine(s.database_url.get_secret_value())
    with Session(engine) as db:
        if db.scalar(
            select(ModelVersion).where(
                ModelVersion.name == pkg["name"], ModelVersion.version == pkg["version"]
            )
        ):
            raise SystemExit("already registered")
        mv = register(db, pkg, uri, a.activate, a.notes)
        print(f"registered {mv.name} {mv.version} status={mv.status} id={mv.id}")


if __name__ == "__main__":
    main()
