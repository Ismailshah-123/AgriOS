"""Write side of the Crop Doctor.

Consistency between storage and database:
  1. every photo is validated and processed in memory first (nothing written yet);
  2. derivatives are written to private storage under generated keys;
  3. rows + audit + analysis job are committed in ONE transaction;
  4. if storage or the database fails, every object written in step 2 is deleted.
A crash between 2 and 3 can leave unreferenced objects; `sweep_orphans` removes them.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.config import Settings
from app.core.errors import AppError
from app.crop_health.images import ImageLimits, ImageRejected, ProcessedImage, process_image
from app.crop_health.models import (
    CaseImage,
    CaseStatus,
    CaseSubmission,
    CropHealthCase,
    InferenceStatus,
    SubmissionKind,
)
from app.crop_health.schemas import SubmissionIn
from app.farms import service as farms
from app.farms.models import CycleStatus
from app.identity.models import User
from app.jobs import queue
from app.storage.base import Storage, StorageError

logger = logging.getLogger("agrios.crop_health")
ANALYSE_JOB = "crop_health.analyse"
KEY_PREFIX = "crop-health"


@dataclass(frozen=True)
class Upload:
    filename: str
    data: bytes


def limits(settings: Settings) -> ImageLimits:
    return ImageLimits(
        settings.upload_max_bytes,
        settings.image_min_side,
        settings.image_max_side,
        settings.image_max_pixels,
        settings.image_store_max_side,
        settings.image_thumb_side,
    )


def _process_all(uploads: list[Upload], settings: Settings) -> list[ProcessedImage]:
    out = []
    for i, up in enumerate(uploads, start=1):
        try:
            out.append(process_image(up.data, limits(settings)))
        except ImageRejected as exc:
            raise AppError(exc.code, f"Photo {i}: {exc.message}", 422, "images") from exc
    return out


def _check_observed_on(sub: SubmissionIn, today: date) -> None:
    if sub.observed_on and not (date(2000, 1, 1) <= sub.observed_on <= today):
        raise AppError(
            "validation_error", "Observation date cannot be in the future.", 422, "observed_on"
        )


def _check_quota(db: Session, user: User, incoming: int, settings: Settings) -> None:
    used = db.scalar(
        select(func.coalesce(func.sum(CaseImage.byte_size), 0))
        .join(CropHealthCase, CropHealthCase.id == CaseImage.case_id)
        .where(CropHealthCase.owner_id == user.id)
    )
    if (used or 0) + incoming > settings.storage_quota_bytes_per_user:
        raise AppError(
            "storage_quota_exceeded", "Your photo storage limit has been reached.", 422, "images"
        )


def _store(storage: Storage, images: list[ProcessedImage]) -> list[tuple[str, str]]:
    now = datetime.now(UTC)
    written: list[str] = []
    keys = []
    try:
        for img in images:
            base = f"{KEY_PREFIX}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}"
            full, thumb = f"{base}-full.webp", f"{base}-thumb.webp"
            storage.put(full, img.full, "image/webp")
            written.append(full)
            storage.put(thumb, img.thumb, "image/webp")
            written.append(thumb)
            keys.append((full, thumb))
    except StorageError as exc:
        _discard(storage, written)
        logger.error("storage_write_failed", extra={"error": str(exc)})
        raise AppError(
            "storage_unavailable", "Photos could not be saved. Please try again.", 503
        ) from exc
    return keys


def _discard(storage: Storage, keys: list[str]) -> None:
    for key in keys:
        try:
            storage.delete(key)
        except StorageError:
            logger.warning("storage_cleanup_failed")  # sweep_orphans will catch it later


def _add_submission(
    db: Session,
    case: CropHealthCase,
    kind: SubmissionKind,
    sub: SubmissionIn,
    images: list[ProcessedImage],
    keys: list[tuple[str, str]],
    now: datetime,
) -> CaseSubmission:
    submission = CaseSubmission(
        case_id=case.id,
        kind=kind,
        plant_part=sub.plant_part,
        symptoms=[s.value for s in sub.symptoms],
        observed_on=sub.observed_on,
        notes=sub.notes,
        submitted_at=now,
    )
    db.add(submission)
    db.flush()
    for pos, (img, (full, thumb)) in enumerate(zip(images, keys, strict=True)):
        db.add(
            CaseImage(
                case_id=case.id,
                submission_id=submission.id,
                position=pos,
                storage_key=full,
                thumb_key=thumb,
                content_type="image/webp",
                original_format=img.original_format,
                width=img.width,
                height=img.height,
                byte_size=len(img.full) + len(img.thumb),
                sha256=img.sha256,
                created_at=now,
            )
        )
    return submission


def _queue_analysis(db: Session, case: CropHealthCase) -> None:
    case.inference_status = InferenceStatus.QUEUED
    case.inference_error_code = None
    queue.enqueue(
        db, kind=ANALYSE_JOB, dedupe_key=f"case:{case.id}", payload={"case_id": str(case.id)}
    )


def create_case(
    db: Session,
    storage: Storage,
    settings: Settings,
    user: User,
    *,
    crop_cycle_id: uuid.UUID,
    sub: SubmissionIn,
    uploads: list[Upload],
    consent_training: bool,
    client_id: str | None,
    rid: str | None,
    today: date,
) -> uuid.UUID:
    cycle, _field, _farm = farms.get_owned_cycle_context(db, user, crop_cycle_id)
    if cycle.status != CycleStatus.ACTIVE:
        raise AppError(
            "cycle_not_active",
            "Choose a crop cycle that is currently growing.",
            422,
            "crop_cycle_id",
        )
    if client_id:  # offline retry: return the case created by the first attempt
        existing = db.scalar(
            select(CropHealthCase.id).where(
                CropHealthCase.owner_id == user.id, CropHealthCase.client_id == client_id
            )
        )
        if existing:
            return existing
    if not 1 <= len(uploads) <= settings.upload_max_images:
        raise AppError(
            "image_count", f"Add between 1 and {settings.upload_max_images} photos.", 422, "images"
        )
    _check_observed_on(sub, today)
    images = _process_all(uploads, settings)
    _check_quota(db, user, sum(len(i.full) + len(i.thumb) for i in images), settings)
    keys = _store(storage, images)
    try:
        # Per-owner numbering; the row lock serialises concurrent creates by one user.
        db.execute(select(User.id).where(User.id == user.id).with_for_update())
        number = (
            db.scalar(
                select(func.max(CropHealthCase.number)).where(CropHealthCase.owner_id == user.id)
            )
            or 0
        ) + 1
        now = datetime.now(UTC)
        case = CropHealthCase(
            owner_id=user.id,
            crop_cycle_id=cycle.id,
            number=number,
            status=CaseStatus.SUBMITTED,
            inference_status=InferenceStatus.NOT_STARTED,
            consent_training=consent_training,
            client_id=client_id,
            last_activity_at=now,
        )
        db.add(case)
        db.flush()
        _add_submission(db, case, SubmissionKind.INITIAL, sub, images, keys, now)
        _queue_analysis(db, case)
        audit.record(
            db,
            action="crop_health_case.created",
            entity="crop_health_case",
            entity_id=case.id,
            actor_id=user.id,
            meta={"images": len(images)},
            request_id=rid,
        )
        db.commit()
        return case.id
    except Exception:
        db.rollback()
        _discard(storage, [k for pair in keys for k in pair])
        raise


def add_follow_up(
    db: Session,
    storage: Storage,
    settings: Settings,
    user: User,
    case: CropHealthCase,
    *,
    sub: SubmissionIn,
    uploads: list[Upload],
    rid: str | None,
    today: date,
) -> None:
    if case.status == CaseStatus.CLOSED:
        raise AppError("case_closed", "This case is closed.", 409)
    if not uploads and sub.is_empty():
        raise AppError("empty_follow_up", "Add a photo or an observation.", 422, "images")
    if len(uploads) > settings.upload_max_images:
        raise AppError(
            "image_count", f"Add at most {settings.upload_max_images} photos.", 422, "images"
        )
    existing = db.scalar(select(func.count()).where(CaseImage.case_id == case.id)) or 0
    if existing + len(uploads) > settings.case_max_images:
        raise AppError(
            "image_count",
            f"A case can hold at most {settings.case_max_images} photos.",
            422,
            "images",
        )
    _check_observed_on(sub, today)
    images = _process_all(uploads, settings)
    _check_quota(db, user, sum(len(i.full) + len(i.thumb) for i in images), settings)
    keys = _store(storage, images) if images else []
    try:
        now = datetime.now(UTC)
        _add_submission(db, case, SubmissionKind.FOLLOW_UP, sub, images, keys, now)
        case.last_activity_at = now
        if images:  # new evidence: analyse again with all photos
            _queue_analysis(db, case)
        audit.record(
            db,
            action="crop_health_case.follow_up",
            entity="crop_health_case",
            entity_id=case.id,
            actor_id=user.id,
            meta={"images": len(images)},
            request_id=rid,
        )
        db.commit()
    except Exception:
        db.rollback()
        _discard(storage, [k for pair in keys for k in pair])
        raise


def retry_analysis(db: Session, user: User, case: CropHealthCase, rid: str | None) -> None:
    if case.inference_status not in (InferenceStatus.FAILED, InferenceStatus.MODEL_UNAVAILABLE):
        raise AppError("analysis_not_retryable", "Analysis is already queued or complete.", 409)
    _queue_analysis(db, case)
    audit.record(
        db,
        action="crop_health_case.analysis_retried",
        entity="crop_health_case",
        entity_id=case.id,
        actor_id=user.id,
        request_id=rid,
    )
    db.commit()


def sweep_orphans(db: Session, storage: Storage, older_than: timedelta = timedelta(hours=1)) -> int:
    """Delete stored objects that no image row references (crash between store and commit)."""
    cutoff = datetime.now(UTC) - older_than
    known = set(db.scalars(select(CaseImage.storage_key))) | set(
        db.scalars(select(CaseImage.thumb_key))
    )
    removed = 0
    for obj in storage.list(KEY_PREFIX):
        if obj.key not in known and obj.modified_at < cutoff:
            storage.delete(obj.key)
            removed += 1
    return removed
