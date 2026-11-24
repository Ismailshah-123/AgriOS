"""FR12 expert review: farmer requests -> expert queue -> recorded outcome.

Rules:
- Only the case owner can request a review; only expert/admin users see the queue.
- Experts see a case only while it awaits review or after an expert reviewed it (they never
  browse other cases). There is no per-expert assignment yet: every expert sees the queue.
- An outcome is human judgement, stored append-only; it never rewrites model predictions.
- needs_retake returns the case to the farmer (status retake); other decisions close it.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator
from sqlalchemy import exists, func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.config import Settings
from app.core.errors import AppError
from app.crop_health import queries
from app.crop_health.models import (
    CaseImage,
    CaseStatus,
    CropHealthCase,
    ExpertReview,
    ReviewDecision,
)
from app.crop_health.schemas import CaseDetail, ReviewOut
from app.farms.models import CropCycle, CropDefinition
from app.identity.models import User

Label = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
REVIEWABLE_FROM = {CaseStatus.SUBMITTED, CaseStatus.RETAKE, CaseStatus.UNSURE,
                   CaseStatus.ACCEPTED, CaseStatus.OUT_OF_SCOPE}  # fmt: skip


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: ReviewDecision
    label: Label | None = None
    note: Note | None = None

    @model_validator(mode="after")
    def _label(self) -> "ReviewIn":
        needs_label = self.decision in (ReviewDecision.CONFIRMED_MODEL, ReviewDecision.DIAGNOSED)
        if needs_label and not self.label:
            raise ValueError("a label is required for this decision")
        return self


class QueueItem(BaseModel):
    case_id: uuid.UUID
    number: int
    crop_name: str
    status: CaseStatus
    waiting_since: datetime
    image_count: int


class ReviewCaseOut(BaseModel):
    case: CaseDetail  # case.expert_reviews holds the review history
    awaiting_review: bool


def reviews_for(db: Session, case_id: uuid.UUID) -> list[ReviewOut]:
    rows = db.execute(
        select(ExpertReview, User.full_name)
        .join(User, User.id == ExpertReview.expert_id)
        .where(ExpertReview.case_id == case_id)
        .order_by(ExpertReview.created_at)
    ).all()
    return [
        ReviewOut(
            id=r.id,
            decision=r.decision,
            label=r.label,
            note=r.note,
            expert_name=name,
            reviewed_at=r.created_at,
        )
        for r, name in rows
    ]


def request_review(db: Session, user: User, case_id: uuid.UUID, rid: str | None) -> None:
    case = queries.get_owned_case(db, user.id, case_id)
    if case.status not in REVIEWABLE_FROM:
        raise AppError("invalid_state", "This case is already with an expert or closed.", 409)
    previous = case.status
    case.status = CaseStatus.EXPERT_REVIEW
    case.last_activity_at = datetime.now(UTC)
    audit.record(
        db,
        action="crop_health_case.expert_requested",
        entity="crop_health_case",
        entity_id=case.id,
        actor_id=user.id,
        meta={"from": previous.value},
        request_id=rid,
    )
    db.commit()


def queue(db: Session) -> list[QueueItem]:
    imgs = (
        select(func.count(CaseImage.id))
        .where(CaseImage.case_id == CropHealthCase.id)
        .correlate(CropHealthCase)
        .scalar_subquery()
    )
    rows = db.execute(
        select(CropHealthCase, CropDefinition.name_en, imgs)
        .join(CropCycle, CropCycle.id == CropHealthCase.crop_cycle_id)
        .join(CropDefinition, CropDefinition.id == CropCycle.crop_id)
        .where(CropHealthCase.status == CaseStatus.EXPERT_REVIEW)
        .order_by(CropHealthCase.last_activity_at)  # oldest first
        .limit(200)
    ).all()
    return [
        QueueItem(
            case_id=c.id,
            number=c.number,
            crop_name=crop,
            status=c.status,
            waiting_since=c.last_activity_at,
            image_count=n,
        )
        for c, crop, n in rows
    ]


def visible_case(db: Session, case_id: uuid.UUID) -> CropHealthCase:
    reviewed = exists().where(ExpertReview.case_id == CropHealthCase.id)
    case = db.scalar(
        select(CropHealthCase).where(
            CropHealthCase.id == case_id,
            (CropHealthCase.status == CaseStatus.EXPERT_REVIEW) | reviewed,
        )
    )
    if case is None:  # not in the queue and never reviewed: invisible to experts
        raise AppError("not_found", "Case not found.", 404)
    return case


def case_for_expert(db: Session, settings: Settings, case_id: uuid.UUID) -> ReviewCaseOut:
    case = visible_case(db, case_id)
    # Photo links are signed for the owner (the file endpoint checks that signature).
    detail = queries.detail(
        db,
        case.owner_id,
        case.id,
        queries.linker(settings, case.owner_id),
        Path(settings.model_path),
    )
    detail.expert_reviews = reviews_for(db, case.id)
    return ReviewCaseOut(case=detail, awaiting_review=case.status == CaseStatus.EXPERT_REVIEW)


def submit_review(
    db: Session, expert: User, case_id: uuid.UUID, data: ReviewIn, rid: str | None
) -> ReviewOut:
    case = visible_case(db, case_id)
    if case.status != CaseStatus.EXPERT_REVIEW:
        raise AppError("invalid_state", "This case is not awaiting expert review.", 409)
    now = datetime.now(UTC)
    review = ExpertReview(
        case_id=case.id,
        expert_id=expert.id,
        decision=data.decision,
        label=data.label,
        note=data.note,
        created_at=now,
    )
    db.add(review)
    case.status = (
        CaseStatus.RETAKE if data.decision == ReviewDecision.NEEDS_RETAKE else CaseStatus.CLOSED
    )
    case.last_activity_at = now
    db.flush()
    audit.record(
        db,
        action="crop_health_case.expert_reviewed",
        entity="crop_health_case",
        entity_id=case.id,
        actor_id=expert.id,
        meta={"decision": data.decision.value, "review_id": str(review.id)},
        request_id=rid,
    )
    db.commit()
    return ReviewOut(
        id=review.id,
        decision=review.decision,
        label=review.label,
        note=review.note,
        expert_name=expert.full_name,
        reviewed_at=now,
    )
