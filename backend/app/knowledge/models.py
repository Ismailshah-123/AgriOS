"""Verified-knowledge store for FR8 (DATABASE_DESIGN Knowledge). Retrieval v1 = PostgreSQL
full-text search (no pgvector on this machine). Only sources whose licence has been
verified by a person are searchable; 'unverified' and 'blocked' sources never are."""

import uuid
from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, REAL, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class SourceReview(StrEnum):
    UNVERIFIED = "unverified"  # default: blocked from ingestion and search
    LICENCE_VERIFIED = "licence_verified"  # a person checked the licence permits this use
    CONTENT_REVIEWED = "content_reviewed"  # licence ok AND content reviewed by an expert
    BLOCKED = "blocked"  # licence does not permit use, or withdrawn


class CommercialUse(StrEnum):
    ALLOWED = "allowed"
    NOT_ALLOWED = "not_allowed"
    UNKNOWN = "unknown"


class IngestStatus(StrEnum):
    NOT_INGESTED = "not_ingested"  # no file yet, or licence not verified
    QUEUED = "queued"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


SEARCHABLE = (SourceReview.LICENCE_VERIFIED, SourceReview.CONTENT_REVIEWED)

# Extensible: a new domain is a new value here + lexicon entries in query.py (no schema change).
DOMAINS = (
    "crop_science",
    "plant_protection",
    "soil_science",
    "nutrient_management",
    "irrigation_water",
    "weather_climate",
    "farm_operations",
    "economics_business",
    "livestock_allied",
    "research_policy",
)
DOCUMENT_TYPES = (
    "extension_guide",
    "factsheet",
    "manual",
    "research_paper",
    "report",
    "policy",
    "standard",
    "dataset",
    "web_page",
    "other",
)


class KnowledgeSource(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        Index(
            "uq_knowledge_sources_file_sha256",
            "file_sha256",
            unique=True,
            postgresql_where=text("file_sha256 IS NOT NULL"),
        ),
    )

    title: Mapped[str] = mapped_column(String(300))
    publisher: Mapped[str] = mapped_column(String(200))
    year: Mapped[int | None] = mapped_column(Integer)
    url: Mapped[str | None] = mapped_column(String(500))
    licence: Mapped[str] = mapped_column(String(120))  # e.g. "CC BY-NC-SA 3.0 IGO" or "unknown"
    licence_url: Mapped[str | None] = mapped_column(String(500))
    commercial_use: Mapped[CommercialUse] = mapped_column(str_enum(CommercialUse, "commercial_use"))
    attribution: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8), default="en")
    region: Mapped[str | None] = mapped_column(String(80))
    review_status: Mapped[SourceReview] = mapped_column(str_enum(SourceReview, "source_review"))
    review_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # 0011: provenance, classification, file and ingestion state
    author: Mapped[str | None] = mapped_column(String(300))
    publication_date: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    country: Mapped[str | None] = mapped_column(String(80))
    domain: Mapped[str | None] = mapped_column(String(40))
    crops: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    document_type: Mapped[str | None] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    file_key: Mapped[str | None] = mapped_column(String(160))
    file_name: Mapped[str | None] = mapped_column(String(255))
    file_mime: Mapped[str | None] = mapped_column(String(100))
    file_bytes: Mapped[int | None] = mapped_column(Integer)
    file_sha256: Mapped[str | None] = mapped_column(String(64))
    ingest_status: Mapped[IngestStatus] = mapped_column(
        str_enum(IngestStatus, "ingest_status"), default=IngestStatus.NOT_INGESTED
    )
    ingest_error: Mapped[str | None] = mapped_column(Text)
    ingest_log: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeChunk(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        Index("ix_knowledge_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_knowledge_chunks_source", "source_id", "position"),
    )

    source_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    section: Mapped[str | None] = mapped_column(String(200))
    text: Mapped[str] = mapped_column(Text)
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(section, '') || ' ' || text)", persisted=True),
    )
    # 0011: dense vector (REAL[]; cosine computed in the app — no pgvector on this host)
    embedding: Mapped[list[float] | None] = mapped_column(ARRAY(REAL))
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    language: Mapped[str | None] = mapped_column(String(8))
    source_version: Mapped[int] = mapped_column(Integer, default=1)


class KnowledgeConversation(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "knowledge_conversations"
    __table_args__ = (Index("ix_knowledge_conversations_user", "user_id", "updated_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeQuery(UUIDPrimaryKeyMixin, Base):
    """One question + answer. Telemetry (latency, status, tokens) and the conversation
    history both come from these rows; nothing is estimated."""

    __tablename__ = "knowledge_queries"
    __table_args__ = (
        Index("ix_knowledge_queries_user", "user_id", "created_at"),
        Index("ix_knowledge_queries_conversation", "conversation_id", "created_at"),
        CheckConstraint(
            "status IN ('answered','extractive','abstained','clarify','error')", name="status"
        ),
        CheckConstraint("feedback_rating IN (-1, 1)", name="feedback"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("knowledge_conversations.id", ondelete="CASCADE")
    )
    question: Mapped[str] = mapped_column(Text)
    retrieval_query: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(8))
    domain: Mapped[str | None] = mapped_column(String(40))
    crops: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    status: Mapped[str] = mapped_column(String(20))  # answered|extractive|abstained|clarify|error
    answer: Mapped[str | None] = mapped_column(Text)
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    n_passages: Mapped[int] = mapped_column(Integer, default=0)
    top_score: Mapped[float | None] = mapped_column(Float)
    retrieval_ms: Mapped[int] = mapped_column(Integer, default=0)
    total_ms: Mapped[int] = mapped_column(Integer, default=0)
    llm_provider: Mapped[str | None] = mapped_column(String(40))
    llm_model: Mapped[str | None] = mapped_column(String(120))
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    feedback_rating: Mapped[int | None] = mapped_column(SmallInteger)  # +1 / -1
    feedback_comment: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
