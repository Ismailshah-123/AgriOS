"""FR12 expert review routes (API_CONTRACTS 'experts': GET /review/queue, POST /review/{id})."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.crop_health import explanation, queries, review
from app.crop_health.schemas import ExplanationOut, ReviewOut
from app.identity.deps import AppSettings, CurrentUser, DbSession, RequestId, require_roles
from app.identity.models import User, UserRole

router = APIRouter(tags=["expert-review"])
Expert = Annotated[User, Depends(require_roles(UserRole.EXPERT, UserRole.ADMIN))]


@router.post("/cases/{case_id}/expert-review", status_code=status.HTTP_204_NO_CONTENT)
def request_expert_review(
    case_id: uuid.UUID, user: CurrentUser, db: DbSession, rid: RequestId
) -> None:
    """Owner asks an expert to look at the case (any non-closed state)."""
    review.request_review(db, user, case_id, rid)


@router.get("/review/queue", response_model=list[review.QueueItem])
def review_queue(expert: Expert, db: DbSession) -> list[review.QueueItem]:
    return review.queue(db)


@router.get("/review/cases/{case_id}", response_model=review.ReviewCaseOut)
def review_case(
    case_id: uuid.UUID, expert: Expert, db: DbSession, settings: AppSettings
) -> review.ReviewCaseOut:
    return review.case_for_expert(db, settings, case_id)


@router.get("/review/cases/{case_id}/explanation", response_model=ExplanationOut)
def review_case_explanation(
    case_id: uuid.UUID, expert: Expert, db: DbSession, settings: AppSettings
) -> ExplanationOut:
    """CAM for the expert view; same visibility rule as the case (queued or reviewed)."""
    case = review.visible_case(db, case_id)
    return explanation.for_case(db, case, queries.linker(settings, case.owner_id))


@router.post(
    "/review/cases/{case_id}", response_model=ReviewOut, status_code=status.HTTP_201_CREATED
)
def submit_review(
    case_id: uuid.UUID, data: review.ReviewIn, expert: Expert, db: DbSession, rid: RequestId
) -> ReviewOut:
    return review.submit_review(db, expert, case_id, data, rid)
