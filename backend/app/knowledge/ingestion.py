"""Source lifecycle: upload -> (licence verified) -> queued -> processing -> indexed | failed.

The ingestion job runs in the background worker (jobs/worker.py HANDLERS). Failures are
recorded on the source (status, error code, processing log) and retried by the job queue's
backoff; the last failure leaves `failed` with the reason. Reprocessing replaces the chunks
atomically. Deleting a source removes its chunks (FK cascade) and its stored file.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.config import Settings
from app.core.errors import AppError
from app.jobs import queue
from app.jobs.models import Job
from app.knowledge import service
from app.knowledge.extract import FORMATS, ExtractionError, detect_format, extract
from app.knowledge.models import SEARCHABLE, IngestStatus, KnowledgeSource, SourceReview
from app.knowledge.providers import get_embedder
from app.storage.base import Storage

logger = logging.getLogger("agrios.knowledge")
INGEST_JOB = "knowledge.ingest"
MAX_LOG = 40


def _now() -> datetime:
    return datetime.now(UTC)


def log(source: KnowledgeSource, event: str, **detail: Any) -> None:
    entry = {"at": _now().isoformat(timespec="seconds"), "event": event, **detail}
    source.ingest_log = [*(source.ingest_log or []), entry][-MAX_LOG:]


def enqueue_ingest(db: Session, source: KnowledgeSource) -> bool:
    """Queue indexing if the source is verified, active and has a file. Returns True if queued."""
    if source.review_status not in SEARCHABLE or not source.is_active or not source.file_key:
        return False
    job_id = queue.enqueue(
        db,
        kind=INGEST_JOB,
        dedupe_key=f"{INGEST_JOB}:{source.id}",
        payload={"source_id": str(source.id), "version": source.version},
    )
    source.ingest_status = IngestStatus.QUEUED
    source.ingest_error = None
    log(source, "queued", job_id=str(job_id) if job_id else "already_queued")
    return True


def attach_file(
    db: Session,
    storage: Storage,
    settings: Settings,
    source: KnowledgeSource,
    filename: str,
    data: bytes,
    actor_id: uuid.UUID,
) -> KnowledgeSource:
    if not data:
        raise AppError("empty_file", "The file is empty.", 422)
    if len(data) > settings.knowledge_upload_max_bytes:
        raise AppError("file_too_large", "The file is larger than the upload limit.", 413)
    try:
        fmt = detect_format(filename, data)
    except ExtractionError as exc:
        raise AppError(str(exc), "Unsupported or mismatched file type.", 415) from exc
    sha = hashlib.sha256(data).hexdigest()
    dup = db.scalar(
        select(KnowledgeSource).where(
            KnowledgeSource.file_sha256 == sha, KnowledgeSource.id != source.id
        )
    )
    if dup is not None:
        raise AppError(
            "duplicate_document", f"This file is already registered as '{dup.title}'.", 409
        )
    old_key = source.file_key
    key = f"knowledge/{source.id.hex}-v{source.version + (1 if old_key else 0)}.{fmt}"
    storage.put(key, data, FORMATS[fmt])
    if old_key:  # a new file is a new version of the same source
        source.version += 1
        storage.delete(old_key)
    source.file_key, source.file_name = key, filename[-255:]
    source.file_mime, source.file_bytes, source.file_sha256 = FORMATS[fmt], len(data), sha
    source.ingest_status = IngestStatus.NOT_INGESTED
    source.updated_at = _now()
    log(source, "file_uploaded", bytes=len(data), format=fmt, version=source.version)
    audit.record(
        db,
        action="knowledge.source.file_uploaded",
        entity="knowledge_source",
        entity_id=source.id,
        actor_id=actor_id,
        meta={"sha256": sha, "bytes": len(data), "version": source.version},
    )
    enqueue_ingest(db, source)
    return source


def handle(db: Session, storage: Storage, settings: Settings, job: Job) -> None:
    """Worker handler. Commits its own outcome."""
    source = db.get(KnowledgeSource, uuid.UUID(job.payload["source_id"]))
    if source is None or not source.file_key or not source.is_active:
        queue.succeed(db, job)  # deleted or deactivated meanwhile: nothing to do
        db.commit()
        return
    if source.review_status not in SEARCHABLE:
        source.ingest_status = IngestStatus.NOT_INGESTED
        log(source, "skipped", reason="licence_not_verified")
        queue.succeed(db, job)
        db.commit()
        return
    source.ingest_status = IngestStatus.PROCESSING
    log(source, "processing", attempt=job.attempts)
    db.commit()
    started = _now()
    try:
        data = storage.get(source.file_key)
        fmt = detect_format(source.file_name or source.file_key, data)
        sections = extract(fmt, data)
        pages = [(s.page, s.heading, s.text) for s in sections]
        embedder = get_embedder(settings)
        n = service.ingest(db, source, pages, embedder=embedder, replace=True)
        if n == 0:
            raise ExtractionError("no_text_found")
    except Exception as exc:
        db.rollback()
        source = db.get(KnowledgeSource, source.id)
        job = db.merge(job)
        code = str(exc) if isinstance(exc, ExtractionError) else exc.__class__.__name__
        if not isinstance(exc, ExtractionError):
            logger.exception("knowledge_ingest_failed", extra={"source_id": str(job.payload)})
        if isinstance(exc, ExtractionError):
            job.attempts = job.max_attempts  # bad file: retrying cannot help
        retry = queue.fail(db, job, code)
        if source is not None:
            source.ingest_status = IngestStatus.QUEUED if retry else IngestStatus.FAILED
            source.ingest_error = code
            log(source, "failed", error=code, will_retry=retry)
        db.commit()
        return
    source.ingest_status = IngestStatus.INDEXED
    source.chunk_count = n
    source.indexed_at = _now()
    source.ingest_error = None
    secs = round((_now() - started).total_seconds(), 2)
    log(
        source,
        "indexed",
        chunks=n,
        sections=len(sections),
        seconds=secs,
        embeddings=embedder.model_name if embedder else None,
    )
    audit.record(
        db,
        action="knowledge.source.indexed",
        entity="knowledge_source",
        entity_id=source.id,
        meta={"chunks": n, "version": source.version},
    )
    queue.succeed(db, job)
    db.commit()


def review(
    db: Session,
    source: KnowledgeSource,
    status: SourceReview,
    note: str | None,
    actor_id: uuid.UUID,
) -> None:
    before = source.review_status
    source.review_status = status
    source.review_note = note
    source.updated_at = _now()
    if status in SEARCHABLE:
        source.verified_by, source.verified_at = actor_id, _now()
    log(source, "review", from_=before.value, to=status.value)
    audit.record(
        db,
        action="knowledge.source.reviewed",
        entity="knowledge_source",
        entity_id=source.id,
        actor_id=actor_id,
        meta={"from": before.value, "to": status.value},
    )
    if status in SEARCHABLE and source.ingest_status in (
        IngestStatus.NOT_INGESTED,
        IngestStatus.FAILED,
    ):
        enqueue_ingest(db, source)


def delete_source(
    db: Session, storage: Storage, source: KnowledgeSource, actor_id: uuid.UUID
) -> None:
    key = source.file_key
    audit.record(
        db,
        action="knowledge.source.deleted",
        entity="knowledge_source",
        entity_id=source.id,
        actor_id=actor_id,
        meta={"title": source.title, "chunks": source.chunk_count},
    )
    db.delete(source)  # chunks: ON DELETE CASCADE
    db.flush()
    if key:
        storage.delete(key)


def ingestion_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(KnowledgeSource.ingest_status, func.count()).group_by(KnowledgeSource.ingest_status)
    ).all()
    by = {s: n for s, n in rows}
    return {s.value: by.get(s, 0) for s in IngestStatus}
