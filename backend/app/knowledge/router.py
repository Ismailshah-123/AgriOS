"""FR8 knowledge API for any signed-in user: ask (RAG), search (passages), conversations,
feedback, cited-source viewer, source register, library stats. Admin routes: router_admin.py."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select

from app.core.errors import AppError
from app.core.rate_limit import SlidingWindowLimiter
from app.identity.deps import AppSettings, CurrentUser, DbSession
from app.knowledge import answer, ingestion, retrieval, service
from app.knowledge.models import (
    DOCUMENT_TYPES,
    DOMAINS,
    SEARCHABLE,
    CommercialUse,
    IngestStatus,
    KnowledgeChunk,
    KnowledgeConversation,
    KnowledgeQuery,
    KnowledgeSource,
    SourceReview,
)
from app.knowledge.providers import get_embedder, provider_status

router = APIRouter(tags=["knowledge"])
NO_GUIDANCE = answer.NO_GUIDANCE["en"]


class PassageOut(BaseModel):
    chunk_id: uuid.UUID
    text: str
    page: int | None
    section: str | None
    rank: float
    dense: float | None = None
    source: dict[str, Any]


class SearchOut(BaseModel):
    query: str
    status: Literal["found", "no_verified_guidance"]
    message: str | None
    passages: list[PassageOut]
    searchable_sources: int
    method: str
    data_origin: Literal["retrieved"] = "retrieved"


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    publisher: str
    author: str | None = None
    year: int | None
    publication_date: Any = None
    retrieved_at: datetime | None = None
    url: str | None
    licence: str
    licence_url: str | None = None
    commercial_use: CommercialUse
    attribution: str | None = None
    language: str
    region: str | None = None
    country: str | None = None
    domain: str | None = None
    crops: list[str] = []
    document_type: str | None = None
    version: int = 1
    is_active: bool = True
    review_status: SourceReview
    review_note: str | None
    verified_at: datetime | None = None
    file_name: str | None = None
    file_bytes: int | None = None
    ingest_status: IngestStatus = IngestStatus.NOT_INGESTED
    ingest_error: str | None = None
    chunk_count: int = 0
    indexed_at: datetime | None = None
    created_at: datetime | None = None


@router.get("/knowledge/search", response_model=SearchOut)
def search(
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    q: Annotated[str, Query(min_length=3, max_length=300)],
) -> SearchOut:
    embedder = get_embedder(settings)
    passages = service.search(db, q, embedder)
    return SearchOut(
        query=q,
        status="found" if passages else "no_verified_guidance",
        message=None if passages else NO_GUIDANCE,
        passages=[PassageOut(**{**p.__dict__}) for p in passages],
        searchable_sources=service.searchable_count(db),
        method=(
            "Hybrid retrieval: PostgreSQL full-text + dense embeddings (RRF); passages are "
            "quoted, never generated"
        )
        if embedder
        else "PostgreSQL full-text search (extractive; passages are quoted, never generated)",
    )


class AskIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=600)
    conversation_id: uuid.UUID | None = None
    language: Literal["auto", "en", "ur"] = "auto"
    domain: Literal[DOMAINS] | None = None  # type: ignore[valid-type]
    crop: str | None = Field(default=None, max_length=40)
    source_id: uuid.UUID | None = None
    document_type: Literal[DOCUMENT_TYPES] | None = None  # type: ignore[valid-type]
    farm_context: Literal["auto", "on", "off"] = "auto"


class AskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    conversation_id: uuid.UUID | None
    question: str
    retrieval_query: str
    language: str
    domain: str | None
    crops: list[str]
    status: str
    answer: str | None
    citations: list[dict[str, Any]]
    meta: dict[str, Any]
    n_passages: int
    retrieval_ms: int
    total_ms: int
    llm_provider: str | None
    llm_model: str | None
    prompt_tokens: int | None
    completion_tokens: int | None
    feedback_rating: int | None
    created_at: datetime | None = None


def _limit(request: Request, user_id: uuid.UUID, per_minute: int) -> None:
    state = request.app.state
    if not hasattr(state, "knowledge_limiter"):
        state.knowledge_limiter = SlidingWindowLimiter(per_minute, 60)
    wait = state.knowledge_limiter.retry_after(str(user_id))
    if wait:
        raise AppError(
            "rate_limited",
            "Too many questions. Please wait a moment.",
            429,
            headers={"Retry-After": str(wait)},
        )
    state.knowledge_limiter.hit(str(user_id))


@router.post("/knowledge/ask", response_model=AskOut)
def ask(
    body: AskIn, request: Request, user: CurrentUser, db: DbSession, settings: AppSettings
) -> KnowledgeQuery:
    _limit(request, user.id, settings.knowledge_ask_limit_per_minute)
    inp = answer.AskInput(
        question=body.question,
        conversation_id=body.conversation_id,
        language=body.language,
        filters=retrieval.Filters(
            domain=body.domain,
            crop=body.crop,
            source_id=body.source_id,
            document_type=body.document_type,
        ),
        farm_context=body.farm_context,
    )
    row = answer.ask(db, settings, user.id, inp)
    db.commit()
    return row


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=500)


@router.post("/knowledge/queries/{query_id}/feedback", status_code=204)
def feedback(query_id: uuid.UUID, body: FeedbackIn, user: CurrentUser, db: DbSession) -> Response:
    row = db.get(KnowledgeQuery, query_id)
    if row is None or row.user_id != user.id:
        raise AppError("not_found", "Answer not found.", 404)
    row.feedback_rating, row.feedback_comment = body.rating, body.comment
    db.commit()
    return Response(status_code=204)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


@router.get("/knowledge/conversations", response_model=list[ConversationOut])
def conversations(user: CurrentUser, db: DbSession) -> list[KnowledgeConversation]:
    return list(
        db.scalars(
            select(KnowledgeConversation)
            .where(KnowledgeConversation.user_id == user.id)
            .order_by(KnowledgeConversation.updated_at.desc())
            .limit(50)
        )
    )


@router.get("/knowledge/conversations/{cid}", response_model=list[AskOut])
def conversation(cid: uuid.UUID, user: CurrentUser, db: DbSession) -> list[KnowledgeQuery]:
    conv = db.get(KnowledgeConversation, cid)
    if conv is None or conv.user_id != user.id:
        raise AppError("not_found", "Conversation not found.", 404)
    return list(
        db.scalars(
            select(KnowledgeQuery)
            .where(KnowledgeQuery.conversation_id == cid)
            .order_by(KnowledgeQuery.created_at)
        )
    )


@router.delete("/knowledge/conversations/{cid}", status_code=204)
def delete_conversation(cid: uuid.UUID, user: CurrentUser, db: DbSession) -> Response:
    conv = db.get(KnowledgeConversation, cid)
    if conv is None or conv.user_id != user.id:
        raise AppError("not_found", "Conversation not found.", 404)
    db.execute(delete(KnowledgeQuery).where(KnowledgeQuery.conversation_id == cid))
    db.delete(conv)
    db.commit()
    return Response(status_code=204)


@router.get("/knowledge/chunks/{chunk_id}")
def open_chunk(chunk_id: uuid.UUID, user: CurrentUser, db: DbSession) -> dict[str, Any]:
    """Open a cited passage with its neighbours (only from searchable, active sources)."""
    c = db.get(KnowledgeChunk, chunk_id)
    s = db.get(KnowledgeSource, c.source_id) if c else None
    if c is None or s is None or s.review_status not in SEARCHABLE or not s.is_active:
        raise AppError("not_found", "Passage not found.", 404)
    near = db.scalars(
        select(KnowledgeChunk)
        .where(
            KnowledgeChunk.source_id == s.id,
            KnowledgeChunk.position.between(c.position - 1, c.position + 1),
        )
        .order_by(KnowledgeChunk.position)
    ).all()
    return {
        "chunk": {"id": str(c.id), "page": c.page, "section": c.section, "text": c.text},
        "context": [
            {
                "id": str(n.id),
                "page": n.page,
                "section": n.section,
                "text": n.text,
                "is_cited": n.id == c.id,
            }
            for n in near
        ],
        "source": {
            **retrieval.source_dict(s),
            "id": str(s.id),
            "licence_url": s.licence_url,
            "attribution": s.attribution,
            "has_file": bool(s.file_key),
        },
        "data_origin": "retrieved",
    }


class StatsOut(BaseModel):
    sources_by_status: dict[str, int]
    searchable_sources: int
    sources_with_chunks: int
    chunks: int
    embedded_chunks: int
    ingestion: dict[str, int]
    last_indexed_at: datetime | None
    queries_total: int
    providers: dict[str, Any]
    not_tracked: list[str]


@router.get("/knowledge/stats", response_model=StatsOut)
def stats(user: CurrentUser, db: DbSession, settings: AppSettings) -> StatsOut:
    """Counts of the real library; telemetry the system does not record is named, not invented."""
    by = dict(
        db.execute(
            select(KnowledgeSource.review_status, func.count()).group_by(
                KnowledgeSource.review_status
            )
        ).all()
    )
    return StatsOut(
        sources_by_status={s.value: by.get(s, 0) for s in SourceReview},
        searchable_sources=service.searchable_count(db),
        sources_with_chunks=db.scalar(select(func.count(func.distinct(KnowledgeChunk.source_id))))
        or 0,
        chunks=db.scalar(select(func.count(KnowledgeChunk.id))) or 0,
        embedded_chunks=db.scalar(
            select(func.count(KnowledgeChunk.id)).where(KnowledgeChunk.embedding.is_not(None))
        )
        or 0,
        ingestion=ingestion.ingestion_counts(db),
        last_indexed_at=db.scalar(select(func.max(KnowledgeSource.indexed_at))),
        queries_total=db.scalar(select(func.count(KnowledgeQuery.id))) or 0,
        providers=provider_status(settings),
        not_tracked=["answer accuracy (needs the evaluation set)", "embedding cost"],
    )


@router.get("/knowledge/sources", response_model=list[SourceOut])
def sources(user: CurrentUser, db: DbSession) -> list[KnowledgeSource]:
    return list(db.scalars(select(KnowledgeSource).order_by(KnowledgeSource.title)))


@router.get("/knowledge/taxonomy")
def taxonomy(user: CurrentUser) -> dict[str, Any]:
    from app.knowledge.query import CROPS

    return {"domains": list(DOMAINS), "document_types": list(DOCUMENT_TYPES), "crops": list(CROPS)}
