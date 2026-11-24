"""Knowledge administration (ADMIN role): register sources, upload files, licence review,
reprocess, (de)activate, delete with index cleanup. Analytics: ADMIN or EXPERT.
Every write is audited (hard rule 9)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import func, select

from app.audit import service as audit
from app.core.errors import AppError
from app.crop_health.router import StorageDep
from app.identity.deps import AppSettings, CurrentUser, DbSession, require_roles
from app.identity.models import User, UserRole
from app.jobs.models import Job
from app.knowledge import ingestion
from app.knowledge.models import (
    DOCUMENT_TYPES,
    DOMAINS,
    SEARCHABLE,
    CommercialUse,
    KnowledgeQuery,
    KnowledgeSource,
    SourceReview,
)
from app.knowledge.router import SourceOut

router = APIRouter(tags=["knowledge-admin"])
Admin = Annotated[User, Depends(require_roles(UserRole.ADMIN))]
Analyst = Annotated[User, Depends(require_roles(UserRole.ADMIN, UserRole.EXPERT))]


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=3, max_length=300)
    publisher: str = Field(min_length=2, max_length=200)
    author: str | None = Field(default=None, max_length=300)
    year: int | None = Field(default=None, ge=1800, le=2100)
    publication_date: date | None = None
    url: HttpUrl | None = None
    licence: str = Field(min_length=2, max_length=120)
    licence_url: HttpUrl | None = None
    commercial_use: CommercialUse = CommercialUse.UNKNOWN
    attribution: str | None = Field(default=None, max_length=2000)
    language: Literal["en", "ur"] = "en"
    region: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, max_length=80)
    domain: Literal[DOMAINS] | None = None  # type: ignore[valid-type]
    crops: list[str] = Field(default_factory=list, max_length=10)
    document_type: Literal[DOCUMENT_TYPES] | None = None  # type: ignore[valid-type]
    retrieved_at: datetime | None = None


class SourcePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=3, max_length=300)
    publisher: str | None = Field(default=None, min_length=2, max_length=200)
    author: str | None = Field(default=None, max_length=300)
    year: int | None = Field(default=None, ge=1800, le=2100)
    publication_date: date | None = None
    licence: str | None = Field(default=None, min_length=2, max_length=120)
    licence_url: HttpUrl | None = None
    attribution: str | None = Field(default=None, max_length=2000)
    region: str | None = Field(default=None, max_length=80)
    country: str | None = Field(default=None, max_length=80)
    domain: Literal[DOMAINS] | None = None  # type: ignore[valid-type]
    crops: list[str] | None = Field(default=None, max_length=10)
    document_type: Literal[DOCUMENT_TYPES] | None = None  # type: ignore[valid-type]
    is_active: bool | None = None


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: SourceReview
    note: str = Field(min_length=5, max_length=2000)  # evidence for the decision is required


class SourceDetail(SourceOut):
    ingest_log: list[dict[str, Any]] = []
    file_sha256: str | None = None


def _get(db: DbSession, sid: uuid.UUID) -> KnowledgeSource:
    s = db.get(KnowledgeSource, sid)
    if s is None:
        raise AppError("not_found", "Source not found.", 404)
    return s


def _clean_crops(crops: list[str]) -> list[str]:
    return sorted({c.strip().lower()[:40] for c in crops if c.strip()})


@router.post("/knowledge/sources", response_model=SourceDetail, status_code=201)
def create_source(body: SourceIn, user: Admin, db: DbSession) -> KnowledgeSource:
    data = body.model_dump()
    data["url"] = str(body.url) if body.url else None
    data["licence_url"] = str(body.licence_url) if body.licence_url else None
    data["crops"] = _clean_crops(body.crops)
    data["retrieved_at"] = body.retrieved_at or datetime.now(UTC)
    s = KnowledgeSource(
        **data,
        review_status=SourceReview.UNVERIFIED,
        created_by=user.id,
        ingest_log=[],
        version=1,
        is_active=True,
        chunk_count=0,
    )
    db.add(s)
    db.flush()
    ingestion.log(s, "registered")
    audit.record(
        db,
        action="knowledge.source.registered",
        entity="knowledge_source",
        entity_id=s.id,
        actor_id=user.id,
        meta={"title": s.title, "licence": s.licence},
    )
    db.commit()
    return s


@router.get("/knowledge/sources/{sid}", response_model=SourceDetail)
def get_source(sid: uuid.UUID, user: CurrentUser, db: DbSession) -> KnowledgeSource:
    return _get(db, sid)


@router.patch("/knowledge/sources/{sid}", response_model=SourceDetail)
def patch_source(sid: uuid.UUID, body: SourcePatch, user: Admin, db: DbSession) -> KnowledgeSource:
    s = _get(db, sid)
    changes = body.model_dump(exclude_unset=True)
    for k in ("licence_url",):
        if changes.get(k) is not None:
            changes[k] = str(changes[k])
    if "crops" in changes and changes["crops"] is not None:
        changes["crops"] = _clean_crops(changes["crops"])
    for k, v in changes.items():
        setattr(s, k, v)
    s.updated_at = datetime.now(UTC)
    ingestion.log(s, "metadata_updated", fields=sorted(changes))
    if changes.get("is_active") is True and s.chunk_count == 0:
        ingestion.enqueue_ingest(db, s)
    audit.record(
        db,
        action="knowledge.source.updated",
        entity="knowledge_source",
        entity_id=s.id,
        actor_id=user.id,
        meta={"fields": sorted(changes)},
    )
    db.commit()
    return s


@router.post("/knowledge/sources/{sid}/review", response_model=SourceDetail)
def review_source(sid: uuid.UUID, body: ReviewIn, user: Admin, db: DbSession) -> KnowledgeSource:
    s = _get(db, sid)
    ingestion.review(db, s, body.status, body.note, user.id)
    db.commit()
    return s


@router.post("/knowledge/sources/{sid}/file", response_model=SourceDetail)
async def upload_file(
    sid: uuid.UUID,
    user: Admin,
    db: DbSession,
    storage: StorageDep,
    settings: AppSettings,
    file: Annotated[UploadFile, File()],
) -> KnowledgeSource:
    s = _get(db, sid)
    data = await file.read(settings.knowledge_upload_max_bytes + 1)
    ingestion.attach_file(db, storage, settings, s, file.filename or "upload.txt", data, user.id)
    db.commit()
    return s


@router.post("/knowledge/sources/{sid}/reprocess", response_model=SourceDetail)
def reprocess(sid: uuid.UUID, user: Admin, db: DbSession) -> KnowledgeSource:
    s = _get(db, sid)
    if s.review_status not in SEARCHABLE:
        raise AppError("licence_not_verified", "Verify the licence before indexing.", 409)
    if not s.file_key:
        raise AppError("no_file", "Upload the document file first.", 409)
    if not s.is_active:
        raise AppError("inactive", "Activate the source first.", 409)
    ingestion.enqueue_ingest(db, s)
    audit.record(
        db,
        action="knowledge.source.reprocess",
        entity="knowledge_source",
        entity_id=s.id,
        actor_id=user.id,
    )
    db.commit()
    return s


@router.delete("/knowledge/sources/{sid}", status_code=204)
def delete_source(sid: uuid.UUID, user: Admin, db: DbSession, storage: StorageDep) -> Response:
    ingestion.delete_source(db, storage, _get(db, sid), user.id)
    db.commit()
    return Response(status_code=204)


@router.get("/knowledge/sources/{sid}/file")
def download_file(
    sid: uuid.UUID, user: CurrentUser, db: DbSession, storage: StorageDep
) -> Response:
    """Original document. Signed-in users only, and only for licence-verified sources
    (admins can also open unverified ones to review them)."""
    s = _get(db, sid)
    if not s.file_key or (s.review_status not in SEARCHABLE and user.role != UserRole.ADMIN):
        raise AppError("not_found", "File not available.", 404)
    data = storage.get(s.file_key)
    name = (s.file_name or "document").replace('"', "")
    return Response(
        data,
        media_type=s.file_mime or "application/octet-stream",
        headers={
            "Content-Disposition": f'inline; filename="{name}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox",
        },
    )


@router.get("/knowledge/analytics")
def analytics(user: Analyst, db: DbSession) -> dict[str, Any]:
    """Measured telemetry from knowledge_queries + ingestion state. No quality percentages."""
    q = KnowledgeQuery
    total = db.scalar(select(func.count(q.id))) or 0
    by_status = dict(db.execute(select(q.status, func.count()).group_by(q.status)).all())
    by_domain = {
        (d or "unclassified"): n
        for d, n in db.execute(select(q.domain, func.count()).group_by(q.domain)).all()
    }
    by_lang = dict(db.execute(select(q.language, func.count()).group_by(q.language)).all())
    pct = func.percentile_cont
    lat = db.execute(
        select(
            pct(0.5).within_group(q.retrieval_ms),
            pct(0.95).within_group(q.retrieval_ms),
            pct(0.5).within_group(q.total_ms),
            pct(0.95).within_group(q.total_ms),
            func.sum(q.prompt_tokens),
            func.sum(q.completion_tokens),
        )
    ).one()
    daily = db.execute(
        select(func.date_trunc("day", q.created_at).label("d"), func.count())
        .group_by("d")
        .order_by("d")
        .limit(60)
    ).all()
    usage = db.execute(
        select(func.jsonb_array_elements(q.citations).op("->>")("title").label("t"), func.count())
        .group_by("t")
        .order_by(func.count().desc())
        .limit(10)
    ).all()
    fb = dict(
        db.execute(
            select(q.feedback_rating, func.count())
            .where(q.feedback_rating.is_not(None))
            .group_by(q.feedback_rating)
        ).all()
    )
    jobs = dict(
        db.execute(
            select(Job.status, func.count())
            .where(Job.kind == ingestion.INGEST_JOB)
            .group_by(Job.status)
        ).all()
    )
    r = lambda v: round(float(v)) if v is not None else None  # noqa: E731
    return {
        "queries_total": total,
        "by_status": by_status,
        "no_result_queries": by_status.get("abstained", 0),
        "failed_queries": by_status.get("error", 0),
        "by_domain": by_domain,
        "by_language": by_lang,
        "latency_ms": {
            "retrieval_p50": r(lat[0]),
            "retrieval_p95": r(lat[1]),
            "total_p50": r(lat[2]),
            "total_p95": r(lat[3]),
        },
        "tokens": {"prompt": int(lat[4] or 0), "completion": int(lat[5] or 0)},
        "daily": [{"day": d.date().isoformat(), "queries": n} for d, n in daily],
        "source_usage": [{"title": t, "citations": n} for t, n in usage if t],
        "feedback": {"helpful": fb.get(1, 0), "not_helpful": fb.get(-1, 0)},
        "ingestion": ingestion.ingestion_counts(db),
        "ingestion_jobs": {getattr(k, "value", str(k)): v for k, v in jobs.items()},
        "not_tracked": [
            "answer accuracy / faithfulness (offline evaluation only)",
            "LLM cost in currency (token counts only)",
        ],
    }
