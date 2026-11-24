"""Deploy start step: fetch + install + register the packaged model if one is configured.

uv run python scripts/fetch_model.py

Reads MODEL_PACKAGE_URL / MODEL_PACKAGE_SHA256 (see app/mlops/package_fetch.py). If unset, it
does nothing (Crop Doctor reports model_unavailable). Idempotent across restarts: files are
re-installed on an ephemeral disk, and the model_versions row is created (and activated, only
when no model is active for the task) the first time, with audit events. Never prints secrets.
Exit 1 on a failed fetch/verification; the start command keeps the API starting regardless.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db import models_registry  # noqa: E402, F401 - complete metadata for FKs
from app.mlops.models import ModelStatus, ModelVersion  # noqa: E402
from app.mlops.package_fetch import PackageError, fetch_and_install  # noqa: E402
from scripts.register_model import register  # noqa: E402


def main() -> int:
    s = get_settings()
    if not (s.model_package_url and s.model_package_sha256):
        print("fetch_model: no model package configured; Crop Doctor stays model_unavailable")
        return 0
    if s.database_url is None:
        print("fetch_model: DATABASE_URL not configured")
        return 1
    try:
        pkg, uri, fresh = fetch_and_install(
            s.model_package_url, s.model_package_sha256, s.model_path
        )
    except (PackageError, OSError, ValueError, KeyError) as exc:
        print(f"fetch_model: not installed ({type(exc).__name__}: {exc})")
        return 1
    print(f"fetch_model: {pkg['name']} {pkg['version']} {'installed' if fresh else 'present'}")
    engine = create_engine(s.database_url.get_secret_value())
    try:
        with Session(engine) as db:
            row = db.scalar(
                select(ModelVersion).where(
                    ModelVersion.name == pkg["name"], ModelVersion.version == pkg["version"]
                )
            )
            if row is not None:
                print(f"fetch_model: already registered (status={row.status})")
                return 0
            has_active = db.scalar(
                select(ModelVersion.id).where(
                    ModelVersion.task == pkg["task"], ModelVersion.status == ModelStatus.ACTIVE
                )
            )
            mv = register(db, pkg, uri, activate=has_active is None, notes="deploy fetch_model")
            print(f"fetch_model: registered {mv.name} {mv.version} status={mv.status}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
