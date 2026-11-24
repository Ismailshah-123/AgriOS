"""Crop Doctor endpoints (API_CONTRACTS "doctor" group + documented Phase 3 additions)."""

import logging
import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status

from app.core.errors import AppError
from app.core.pagination import DEFAULT_LIMIT, Cursor, Limit, Page
from app.core.rate_limit import SlidingWindowLimiter
from app.crop_health import explanation, queries, review, service
from app.crop_health.models import CaseStatus, InferenceStatus, PlantPart, Symptom
from app.crop_health.schemas import (
    AnalysisOut,
    CaseDetail,
    CaseListItem,
    CaseStats,
    ExplanationOut,
    SubmissionIn,
)
from app.identity.deps import AppSettings, CurrentUser, DbSession, RequestId
from app.mlops import registry
from app.storage import signing
from app.storage.base import Storage, StorageError

logger = logging.getLogger("agrios.crop_health")
router = APIRouter(tags=["crop-doctor"])


def get_storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


StorageDep = Annotated[Storage, Depends(get_storage)]
Images = Annotated[list[UploadFile], File(description="JPEG, PNG or WebP photos")]


def _read(files: list[UploadFile], max_bytes: int) -> list[service.Upload]:
    uploads = []
    for i, f in enumerate(files, start=1):
        data = f.file.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise AppError(
                "image_too_large",
                f"Photo {i}: each photo must be {max_bytes // (1024 * 1024)} MB or smaller.",
                422,
                "images",
            )
        uploads.append(service.Upload(filename=f.filename or "", data=data))
    return uploads


def _submission(
    plant_part: PlantPart | None,
    symptoms: list[Symptom],
    observed_on: date | None,
    notes: str | None,
) -> SubmissionIn:
    return SubmissionIn(
        plant_part=plant_part, symptoms=symptoms, observed_on=observed_on, notes=notes
    )


def _limit_creates(request: Request, user_id: uuid.UUID, per_hour: int) -> None:
    state = request.app.state
    if not hasattr(state, "case_limiter"):
        state.case_limiter = SlidingWindowLimiter(per_hour, 3600)
    wait = state.case_limiter.retry_after(str(user_id))
    if wait:
        raise AppError(
            "rate_limited",
            "Too many new cases. Please try again later.",
            429,
            headers={"Retry-After": str(wait)},
        )
    state.case_limiter.hit(str(user_id))


@router.post("/cases", response_model=CaseDetail, status_code=status.HTTP_201_CREATED)
def create_case(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
    settings: AppSettings,
    rid: RequestId,
    images: Images,
    crop_cycle_id: Annotated[uuid.UUID, Form()],
    plant_part: Annotated[PlantPart | None, Form()] = None,
    symptoms: Annotated[list[Symptom], Form()] = [],  # noqa: B006 - FastAPI form list
    observed_on: Annotated[date | None, Form()] = None,
    notes: Annotated[str | None, Form(max_length=2000)] = None,
    consent_training: Annotated[bool, Form()] = False,
    client_id: Annotated[str | None, Form(pattern=r"^[A-Za-z0-9_-]{8,64}$")] = None,
) -> CaseDetail:
    _limit_creates(request, user.id, settings.case_create_limit_per_hour)
    case_id = service.create_case(
        db,
        storage,
        settings,
        user,
        crop_cycle_id=crop_cycle_id,
        sub=_submission(plant_part, symptoms, observed_on, notes),
        uploads=_read(images, settings.upload_max_bytes),
        consent_training=consent_training,
        client_id=client_id,
        rid=rid,
        today=date.today(),
    )
    return queries.detail(
        db, user.id, case_id, queries.linker(settings, user.id), settings.model_path
    )


@router.get("/cases", response_model=Page[CaseListItem])
def list_cases(
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    status_: Annotated[CaseStatus | None, Query(alias="status")] = None,
    inference_status: InferenceStatus | None = None,
    crop_id: uuid.UUID | None = None,
    farm_id: uuid.UUID | None = None,
    field_id: uuid.UUID | None = None,
    crop_cycle_id: uuid.UUID | None = None,
    needs_follow_up: bool = False,
    created_from: date | None = None,
    created_to: date | None = None,
    q: Annotated[str | None, Query(max_length=80)] = None,
    limit: Limit = DEFAULT_LIMIT,
    cursor: Cursor = None,
) -> Page[CaseListItem]:
    return queries.list_cases(
        db,
        user.id,
        queries.linker(settings, user.id),
        limit=limit,
        cursor=cursor,
        status=status_,
        inference_status=inference_status,
        crop_id=crop_id,
        farm_id=farm_id,
        field_id=field_id,
        crop_cycle_id=crop_cycle_id,
        needs_follow_up=needs_follow_up,
        created_from=created_from,
        created_to=created_to,
        q=q,
    )


@router.get("/cases/summary", response_model=CaseStats)
def case_summary(user: CurrentUser, db: DbSession, settings: AppSettings) -> CaseStats:
    return queries.stats(db, user.id, settings.model_path)


@router.get("/cases/{case_id}", response_model=CaseDetail)
def get_case(
    case_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings
) -> CaseDetail:
    detail = queries.detail(
        db, user.id, case_id, queries.linker(settings, user.id), settings.model_path
    )
    detail.expert_reviews = review.reviews_for(db, case_id)
    return detail


@router.post(
    "/cases/{case_id}/follow-ups", response_model=CaseDetail, status_code=status.HTTP_201_CREATED
)
def add_follow_up(
    case_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    storage: StorageDep,
    settings: AppSettings,
    rid: RequestId,
    images: Annotated[list[UploadFile], File()] = [],  # noqa: B006
    plant_part: Annotated[PlantPart | None, Form()] = None,
    symptoms: Annotated[list[Symptom], Form()] = [],  # noqa: B006
    observed_on: Annotated[date | None, Form()] = None,
    notes: Annotated[str | None, Form(max_length=2000)] = None,
) -> CaseDetail:
    case = queries.get_owned_case(db, user.id, case_id)
    service.add_follow_up(
        db,
        storage,
        settings,
        user,
        case,
        sub=_submission(plant_part, symptoms, observed_on, notes),
        uploads=_read(images, settings.upload_max_bytes),
        rid=rid,
        today=date.today(),
    )
    return queries.detail(
        db, user.id, case_id, queries.linker(settings, user.id), settings.model_path
    )


@router.get("/cases/{case_id}/analysis", response_model=AnalysisOut)
def get_analysis(
    case_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings
) -> AnalysisOut:
    return queries.analysis(db, queries.get_owned_case(db, user.id, case_id), settings.model_path)


@router.get("/cases/{case_id}/explanation", response_model=ExplanationOut)
def get_explanation(
    case_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings
) -> ExplanationOut:
    case = queries.get_owned_case(db, user.id, case_id)  # 404 for anyone but the owner
    return explanation.for_case(db, case, queries.linker(settings, user.id))


@router.post("/cases/{case_id}/analysis/retry", response_model=AnalysisOut)
def retry_analysis(
    case_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings, rid: RequestId
) -> AnalysisOut:
    case = queries.get_owned_case(db, user.id, case_id)
    service.retry_analysis(db, user, case, rid)
    return queries.analysis(db, case, settings.model_path)


@router.get("/models/availability", tags=["models"])
def model_availability(_: CurrentUser, db: DbSession, settings: AppSettings) -> dict[str, Any]:
    """Model status + its saved evaluation summary (test / external set metrics). These
    describe the MODEL on held-out sets; they are not the confidence of any one photo."""
    a = registry.availability(db, settings.model_path)
    m = a.model
    cfg = (m.config or {}) if m else {}
    return {
        "task": registry.CROP_HEALTH_TASK,
        "status": a.status,
        "reason": a.reason,
        "model_name": m.name if m else None,
        "model_version": m.version if m else None,
        "arch": m.arch if m else None,
        "supported_crops": m.supported_crops if m else [],
        "classes": [lbl["label"] for lbl in m.labels] if m else [],
        "metrics_summary": cfg.get("metrics_summary"),
        "threshold_policy": cfg.get("threshold_policy"),
        "metrics_ref": m.metrics_ref if m else None,
    }


@router.get("/files/case-images/{image_id}/{variant}", include_in_schema=False)
def case_image_file(
    image_id: uuid.UUID,
    variant: Literal["full", "thumb"],
    db: DbSession,
    storage: StorageDep,
    settings: AppSettings,
    exp: Annotated[int, Query()],
    sig: Annotated[str, Query(max_length=64)],
) -> Response:
    """Signed, short-lived link. Every failure is the same 404 (no existence oracle)."""
    not_found = AppError("not_found", "Image not found.", 404)
    found = queries.image_for_file(db, image_id)
    secret = settings.jwt_secret.get_secret_value() if settings.jwt_secret else None
    if found is None or secret is None:
        raise not_found
    image, owner_id = found
    if not signing.verify(image_id, variant, owner_id, exp, sig, secret):
        raise not_found
    try:
        data = storage.get(image.storage_key if variant == "full" else image.thumb_key)
    except (FileNotFoundError, StorageError):
        logger.error("case_image_unreadable", extra={"image_id": str(image_id)})
        raise not_found from None
    return Response(
        content=data,
        media_type="image/webp",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
            "Content-Security-Policy": "default-src 'none'",
        },
    )
