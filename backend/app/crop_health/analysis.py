"""Crop-health analysis job handler (runs in the worker, never in a request).

Outcomes:
  model not ready        -> inference_status=model_unavailable (+ reason code); job succeeds
                            because retrying cannot help. NO prediction row is written.
  crop not supported     -> model_unavailable with code "crop_not_supported"; no prediction.
  predictor/output error -> full rollback (no partial rows), job retried with backoff;
                            after the last attempt inference_status=failed. Photos and case
                            data are never modified by a failed attempt.
  success                -> one diagnosis_predictions row (with model_version_id), case
                            status = decision (accepted | unsure | out_of_scope), audit event.
"""

import logging
import time
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.config import Settings
from app.crop_health.models import (
    CaseImage,
    CaseStatus,
    CropHealthAnalysis,
    CropHealthCase,
    InferenceStatus,
)
from app.farms.models import CropCycle, CropDefinition
from app.jobs import queue
from app.jobs.models import Job
from app.mlops import registry
from app.mlops.predictor import ModelInput, decide
from app.storage.base import Storage

logger = logging.getLogger("agrios.crop_health.analysis")


def _f(v: Decimal | None) -> float | None:
    return float(v) if v is not None else None


def handle(db: Session, storage: Storage, settings: Settings, job: Job) -> None:
    case = db.get(CropHealthCase, uuid.UUID(job.payload["case_id"]))
    if case is None:  # case removed since queuing: nothing to do
        queue.succeed(db, job)
        db.commit()
        return
    case.inference_status = InferenceStatus.RUNNING
    db.commit()

    avail = registry.availability(db, settings.model_path)
    crop_code = db.scalar(
        select(CropDefinition.code)
        .join(CropCycle, CropCycle.crop_id == CropDefinition.id)
        .where(CropCycle.id == case.crop_cycle_id)
    )
    if avail.status != "ready" or avail.model is None:
        _unavailable(db, case, job, avail.status)
        return
    model = avail.model
    if crop_code not in model.supported_crops:
        _unavailable(db, case, job, "crop_not_supported")
        return

    images = list(
        db.scalars(
            select(CaseImage)
            .where(CaseImage.case_id == case.id)
            .order_by(CaseImage.created_at, CaseImage.position)
        )
    )
    started = time.perf_counter()
    try:
        predictor = registry.load_predictor(model, settings.model_path)
        raw = predictor.predict(
            ModelInput(
                images=[storage.get(i.storage_key) for i in images], crop_code=crop_code or ""
            )
        )
        d = decide(
            raw,
            [lbl["label"] for lbl in model.labels],
            _f(model.temperature),
            _f(model.threshold),
            _f(model.ood_threshold),
        )
    except Exception as exc:  # noqa: BLE001 - any model failure is contained here
        db.rollback()
        code = f"inference_error:{exc.__class__.__name__}"
        logger.warning(
            "crop_health_inference_failed", extra={"case_id": str(case.id), "code": code}
        )
        job = db.merge(job)
        case = db.merge(case)
        retrying = queue.fail(db, job, code)
        case.inference_status = InferenceStatus.QUEUED if retrying else InferenceStatus.FAILED
        case.inference_error_code = None if retrying else code[:64]
        db.commit()
        return

    now = datetime.now(UTC)
    db.add(
        CropHealthAnalysis(
            case_id=case.id,
            model_version_id=model.id,
            decision=CaseStatus(d.decision),
            predicted_class=d.predicted_class,
            calibrated_conf=Decimal(str(d.calibrated_conf)),
            ood_score=Decimal(str(d.ood_score)),
            probs=d.probs,
            shortlist=d.shortlist,
            image_ids=[str(i.id) for i in images],
            explanation=raw.explanation,
            context_used="none",
            duration_ms=int((time.perf_counter() - started) * 1000),
            created_at=now,
        )
    )
    if case.status not in (CaseStatus.EXPERT_REVIEW, CaseStatus.CLOSED):
        case.status = CaseStatus(d.decision)  # never pull a case out of expert review
    case.inference_status = InferenceStatus.COMPLETED
    case.inference_error_code = None
    audit.record(
        db,
        action="crop_health_case.analysed",
        entity="crop_health_case",
        entity_id=case.id,
        meta={"model_version_id": str(model.id), "decision": d.decision},
    )
    queue.succeed(db, job)
    db.commit()


def _unavailable(db: Session, case: CropHealthCase, job: Job, reason: str) -> None:
    case.inference_status = InferenceStatus.MODEL_UNAVAILABLE
    case.inference_error_code = reason[:64]
    queue.succeed(db, job)
    db.commit()
