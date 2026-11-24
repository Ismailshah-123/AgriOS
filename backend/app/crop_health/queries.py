"""Read side of the Crop Doctor: owner-scoped queries and output mapping.

Every query filters on `diagnosis_cases.owner_id = user`; a foreign id is simply not
found (404). Image links are short-lived signed URLs; storage keys never leave the API.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.core.pagination import Page, paginate, to_page
from app.crop_health.models import (
    CaseImage,
    CaseStatus,
    CaseSubmission,
    CropHealthAnalysis,
    CropHealthCase,
    InferenceStatus,
)
from app.crop_health.schemas import (
    AnalysisOut,
    CaseDetail,
    CaseListItem,
    CaseStats,
    CropRef,
    ImageOut,
    PredictionOut,
    Ref,
    SubmissionOut,
    TimelineEvent,
)
from app.farms.models import CropCycle, CropDefinition, Farm, Field
from app.mlops import registry
from app.mlops.models import ModelVersion
from app.storage import signing

API = "/api/v1"
LIMITS_NOTE = (
    "Decision support only. Based on photos alone; it can be wrong, especially for "
    "unusual images or conditions. Confirm with an expert before acting."
)
NEEDS_FOLLOW_UP = (CaseStatus.RETAKE, CaseStatus.UNSURE, CaseStatus.EXPERT_REVIEW)
TIMELINE_STATUS = {
    InferenceStatus.NOT_STARTED: "Analysis not started",
    InferenceStatus.QUEUED: "Queued for analysis",
    InferenceStatus.RUNNING: "Analysis in progress",
    InferenceStatus.COMPLETED: "Analysis completed",
    InferenceStatus.FAILED: "Analysis failed",
    InferenceStatus.MODEL_UNAVAILABLE: "Analysis unavailable: no validated model installed",
}
AWAITING = (InferenceStatus.QUEUED, InferenceStatus.RUNNING, InferenceStatus.MODEL_UNAVAILABLE)


def reference(number: int) -> str:
    return f"CD-{number:06d}"


def _base(owner_id: uuid.UUID) -> Select[Any]:
    images = (
        select(CaseImage.case_id, func.count(CaseImage.id).label("n"))
        .group_by(CaseImage.case_id)
        .subquery()
    )
    subs = (
        select(CaseSubmission.case_id, func.count(CaseSubmission.id).label("n"))
        .group_by(CaseSubmission.case_id)
        .subquery()
    )
    return (
        select(
            CropHealthCase,
            CropCycle,
            Field,
            Farm,
            CropDefinition,
            func.coalesce(images.c.n, 0),
            func.coalesce(subs.c.n, 0),
        )
        .join(CropCycle, CropCycle.id == CropHealthCase.crop_cycle_id)
        .join(Field, Field.id == CropCycle.field_id)
        .join(Farm, Farm.id == Field.farm_id)
        .join(CropDefinition, CropDefinition.id == CropCycle.crop_id)
        .outerjoin(images, images.c.case_id == CropHealthCase.id)
        .outerjoin(subs, subs.c.case_id == CropHealthCase.id)
        .where(CropHealthCase.owner_id == owner_id, Farm.owner_id == owner_id)
    )


@dataclass(frozen=True)
class Linker:
    secret: str
    ttl: int
    owner_id: uuid.UUID

    def image(self, img: CaseImage) -> ImageOut:
        urls = {}
        exp = 0
        for variant in ("full", "thumb"):
            exp, sig = signing.sign(img.id, variant, self.owner_id, self.ttl, self.secret)
            urls[variant] = f"{API}/files/case-images/{img.id}/{variant}?exp={exp}&sig={sig}"
        return ImageOut(
            id=img.id,
            position=img.position,
            width=img.width,
            height=img.height,
            url=urls["full"],
            thumb_url=urls["thumb"],
            urls_expire_at=datetime.fromtimestamp(exp, UTC),
        )


def linker(settings: Settings, owner_id: uuid.UUID) -> Linker:
    if settings.jwt_secret is None:
        raise AppError("auth_not_configured", "Authentication is not configured.", 503)
    return Linker(settings.jwt_secret.get_secret_value(), settings.signed_url_seconds, owner_id)


def _first_thumbs(db: Session, case_ids: list[uuid.UUID]) -> dict[uuid.UUID, CaseImage]:
    if not case_ids:
        return {}
    rows = db.scalars(
        select(CaseImage)
        .where(CaseImage.case_id.in_(case_ids))
        .order_by(CaseImage.case_id, CaseImage.created_at, CaseImage.position)
        .distinct(CaseImage.case_id)
    )
    return {img.case_id: img for img in rows}


def _item(row: Any, link: Linker, thumbs: dict[uuid.UUID, CaseImage]) -> dict[str, Any]:
    case, cycle, field, farm, crop, n_images, n_subs = row
    thumb = thumbs.get(case.id)
    return {
        "id": case.id,
        "reference": reference(case.number),
        "status": case.status,
        "inference_status": case.inference_status,
        "crop": CropRef(id=crop.id, code=crop.code, name=crop.name_en),
        "farm": Ref(id=farm.id, name=farm.name),
        "field": Ref(id=field.id, name=field.name),
        "crop_cycle_id": cycle.id,
        "image_count": n_images,
        "submission_count": n_subs,
        "thumb_url": link.image(thumb).thumb_url if thumb else None,
        "created_at": case.created_at,
        "last_activity_at": case.last_activity_at,
    }


def list_cases(
    db: Session, owner_id: uuid.UUID, link: Linker, *, limit: int, cursor: str | None, **f: Any
) -> Page[CaseListItem]:
    stmt = _base(owner_id)
    for col, key in (
        (CropHealthCase.status, "status"),
        (CropHealthCase.inference_status, "inference_status"),
        (CropDefinition.id, "crop_id"),
        (Farm.id, "farm_id"),
        (Field.id, "field_id"),
        (CropCycle.id, "crop_cycle_id"),
    ):
        if f.get(key) is not None:
            stmt = stmt.where(col == f[key])
    if f.get("needs_follow_up"):
        stmt = stmt.where(CropHealthCase.status.in_(NEEDS_FOLLOW_UP))
    if f.get("created_from"):
        stmt = stmt.where(
            CropHealthCase.created_at >= datetime.combine(f["created_from"], time.min, UTC)
        )
    if f.get("created_to"):
        stmt = stmt.where(
            CropHealthCase.created_at <= datetime.combine(f["created_to"], time.max, UTC)
        )
    if q := (f.get("q") or "").strip():
        digits = "".join(c for c in q if c.isdigit())
        conds = [
            Field.name.icontains(q, autoescape=True),
            Farm.name.icontains(q, autoescape=True),
            CropDefinition.name_en.icontains(q, autoescape=True),
        ]
        if digits:
            conds.append(CropHealthCase.number == int(digits[:9]))
        stmt = stmt.where(or_(*conds))
    rows = db.execute(paginate(stmt, CropHealthCase, limit, cursor)).all()
    thumbs = _first_thumbs(db, [r[0].id for r in rows])
    return to_page([CaseListItem(**_item(r, link, thumbs)) for r in rows], limit)


def get_owned_case(db: Session, owner_id: uuid.UUID, case_id: uuid.UUID) -> CropHealthCase:
    case = db.scalar(
        select(CropHealthCase).where(
            CropHealthCase.id == case_id, CropHealthCase.owner_id == owner_id
        )
    )
    if case is None:
        raise AppError("not_found", "Case not found.", 404)
    return case


def analysis(db: Session, case: CropHealthCase, model_root: Path) -> AnalysisOut:
    avail = registry.availability(db, model_root)
    latest = db.execute(
        select(CropHealthAnalysis, ModelVersion)
        .join(ModelVersion, ModelVersion.id == CropHealthAnalysis.model_version_id)
        .where(CropHealthAnalysis.case_id == case.id)
        .order_by(CropHealthAnalysis.created_at.desc())
        .limit(1)
    ).first()
    result = None
    # A result is shown ONLY when inference completed; never for queued/failed/unavailable.
    if latest and case.inference_status == InferenceStatus.COMPLETED:
        a, mv = latest
        result = PredictionOut(
            decision=a.decision,
            predicted_class=a.predicted_class,
            calibrated_confidence=float(a.calibrated_conf),
            ood_score=float(a.ood_score) if a.ood_score is not None else None,
            shortlist=a.shortlist,
            model_name=mv.name,
            model_version=mv.version,
            analysed_at=a.created_at,
            image_count=len(a.image_ids),
            explanation_available=bool(a.explanation) and a.decision != CaseStatus.OUT_OF_SCOPE,
            limits_note=LIMITS_NOTE,
        )
    messages = {
        InferenceStatus.NOT_STARTED: "Analysis has not started.",
        InferenceStatus.QUEUED: "Waiting for analysis.",
        InferenceStatus.RUNNING: "Analysing photos.",
        InferenceStatus.COMPLETED: "Analysis complete.",
        InferenceStatus.FAILED: "Analysis could not be completed. Your photos are saved.",
        InferenceStatus.MODEL_UNAVAILABLE: (
            "No validated analysis model is installed yet. Your photos are saved and can "
            "be analysed once a model is available."
        ),
    }
    message = messages[case.inference_status]
    if case.inference_error_code == "crop_not_supported":
        # A model may be installed: say why there is no diagnosis instead of "no model".
        message = (
            "The installed model does not support this crop, so no diagnosis is given. "
            "Your photos are saved and an expert can review them."
        )
    return AnalysisOut(
        inference_status=case.inference_status,
        model_availability=avail.status,
        error_code=case.inference_error_code,
        message=message,
        can_retry=case.inference_status
        in (InferenceStatus.FAILED, InferenceStatus.MODEL_UNAVAILABLE),
        result=result,
    )


def detail(
    db: Session, owner_id: uuid.UUID, case_id: uuid.UUID, link: Linker, model_root: Path
) -> CaseDetail:
    row = db.execute(_base(owner_id).where(CropHealthCase.id == case_id)).first()
    if row is None:
        raise AppError("not_found", "Case not found.", 404)
    case = row[0]
    subs = list(
        db.scalars(
            select(CaseSubmission)
            .where(CaseSubmission.case_id == case.id)
            .order_by(CaseSubmission.submitted_at)
        )
    )
    imgs = list(
        db.scalars(
            select(CaseImage)
            .where(CaseImage.case_id == case.id)
            .order_by(CaseImage.created_at, CaseImage.position)
        )
    )
    by_sub: dict[uuid.UUID, list[ImageOut]] = {}
    for img in imgs:
        by_sub.setdefault(img.submission_id, []).append(link.image(img))
    submissions = [
        SubmissionOut(
            id=s.id,
            kind=s.kind,
            plant_part=s.plant_part,
            symptoms=s.symptoms,
            observed_on=s.observed_on,
            notes=s.notes,
            submitted_at=s.submitted_at,
            images=by_sub.get(s.id, []),
        )
        for s in subs
    ]
    an = analysis(db, case, model_root)
    timeline = [
        TimelineEvent(
            at=s.submitted_at,
            kind="created" if i == 0 else "follow_up",
            text="Case submitted" if i == 0 else "Follow-up added",
        )
        for i, s in enumerate(subs)
    ]
    if an.result:
        timeline.append(
            TimelineEvent(
                at=an.result.analysed_at, kind="analysis_completed", text="Analysis completed"
            )
        )
    else:
        timeline.append(
            # DB updated_at (transaction time) can precede app-side submission times.
            TimelineEvent(
                at=max(case.updated_at, case.last_activity_at),
                kind="analysis_status",
                text=TIMELINE_STATUS[case.inference_status],
            )
        )
    timeline.sort(key=lambda e: e.at)
    thumbs = {case.id: imgs[0]} if imgs else {}
    return CaseDetail(
        **_item(row, link, thumbs),
        consent_training=case.consent_training,
        submissions=submissions,
        analysis=an,
        timeline=timeline,
    )


def stats(db: Session, owner_id: uuid.UUID, model_root: Path) -> CaseStats:
    by_inf = dict(
        db.execute(
            select(CropHealthCase.inference_status, func.count())
            .where(CropHealthCase.owner_id == owner_id)
            .group_by(CropHealthCase.inference_status)
        ).all()
    )
    follow = db.scalar(
        select(func.count()).where(
            CropHealthCase.owner_id == owner_id, CropHealthCase.status.in_(NEEDS_FOLLOW_UP)
        )
    )
    return CaseStats(
        total=sum(by_inf.values()),
        awaiting_analysis=sum(by_inf.get(s, 0) for s in AWAITING),
        needs_follow_up=follow or 0,
        by_inference_status={s: by_inf.get(s, 0) for s in InferenceStatus},
        model_availability=registry.availability(db, model_root).status,
    )


def image_for_file(db: Session, image_id: uuid.UUID) -> tuple[CaseImage, uuid.UUID] | None:
    row = db.execute(
        select(CaseImage, CropHealthCase.owner_id)
        .join(CropHealthCase, CropHealthCase.id == CaseImage.case_id)
        .where(CaseImage.id == image_id)
    ).first()
    return (row[0], row[1]) if row else None
