"""Job queue operations. All state lives in PostgreSQL, so a crash never loses a job:
a RUNNING job whose worker died is reclaimed after `stale_after`."""

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.jobs.models import Job, JobStatus

BACKOFF_SECONDS = (10, 60, 300)


def enqueue(
    db: Session, *, kind: str, dedupe_key: str, payload: dict[str, Any], max_attempts: int = 3
) -> uuid.UUID | None:
    """Insert a job unless an identical one is already queued/running. Returns its id,
    or None when a duplicate was suppressed. Does not commit (caller's transaction)."""
    stmt = (
        insert(Job)
        .values(
            id=uuid.uuid4(),
            kind=kind,
            dedupe_key=dedupe_key,
            payload=payload,
            status=JobStatus.QUEUED,
            max_attempts=max_attempts,
        )
        .on_conflict_do_nothing(
            index_elements=["dedupe_key"],
            index_where=text("status IN ('queued', 'running')"),
        )
        .returning(Job.id)
    )
    return db.execute(stmt).scalar_one_or_none()


def claim(
    db: Session, worker_id: str, kinds: list[str], stale_after: timedelta = timedelta(minutes=10)
) -> Job | None:
    """Atomically take one due job (FOR UPDATE SKIP LOCKED). Commits the claim.

    All times use the DATABASE clock (run_after is written with clock_timestamp()); mixing
    in the app server's clock made fresh jobs look "not due" under tiny clock skew.
    """
    now = db.scalar(select(func.clock_timestamp()))
    job = db.scalar(
        select(Job)
        .where(
            Job.kind.in_(kinds),
            or_(
                (Job.status == JobStatus.QUEUED) & (Job.run_after <= now),
                (Job.status == JobStatus.RUNNING) & (Job.started_at < now - stale_after),
            ),
        )
        .order_by(Job.run_after)
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    if job is None:
        return None
    job.status = JobStatus.RUNNING
    job.attempts += 1
    job.started_at = now
    job.locked_by = worker_id
    db.commit()
    return job


def _db_now(db: Session) -> datetime:
    return db.scalar(select(func.clock_timestamp()))  # type: ignore[return-value]


def succeed(db: Session, job: Job) -> None:
    job.status = JobStatus.SUCCEEDED
    job.finished_at = _db_now(db)
    job.last_error = None


def fail(db: Session, job: Job, error_code: str) -> bool:
    """Record a failure. Returns True if the job will be retried."""
    job.last_error = error_code[:200]
    if job.attempts < job.max_attempts:
        delay = BACKOFF_SECONDS[min(job.attempts - 1, len(BACKOFF_SECONDS) - 1)]
        job.status = JobStatus.QUEUED
        job.run_after = _db_now(db) + timedelta(seconds=delay)
        return True
    job.status = JobStatus.FAILED
    job.finished_at = _db_now(db)
    return False
