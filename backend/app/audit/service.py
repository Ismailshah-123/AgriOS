"""Audit service. Every module records important actions through `record()`, inside the
same transaction as the change it describes (so the audit row commits or rolls back
with it)."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent


def recent_for_actor(
    db: Session, actor_id: uuid.UUID, entities: tuple[str, ...], limit: int
) -> list[AuditEvent]:
    """The user's own recent actions on the given entity types, newest first."""
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.actor_id == actor_id, AuditEvent.entity.in_(entities))
        .order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


_FORBIDDEN_META_KEYS = {"password", "password_hash", "token", "access_token", "refresh_token"}


def record(
    db: Session,
    *,
    action: str,
    entity: str,
    entity_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    meta: dict[str, Any] | None = None,
    request_id: str | None = None,
) -> AuditEvent:
    meta = meta or {}
    leaked = _FORBIDDEN_META_KEYS & set(meta)
    if leaked:  # programming error: secrets must never reach the audit log
        raise ValueError(f"audit meta must not contain {sorted(leaked)}")
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        meta=meta,
        request_id=request_id,
    )
    db.add(event)
    return event
