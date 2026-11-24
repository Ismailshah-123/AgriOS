"""Append-only audit trail. A database trigger (migration 0001) rejects DELETE and any
UPDATE except clearing `actor_id` when a user account is removed."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_actor_time", "actor_id", "created_at"),
        Index("ix_audit_events_entity", "entity", "entity_id"),
    )

    actor_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None]
    # Identifiers and changed field NAMES only; never passwords, tokens or free text.
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    request_id: Mapped[str | None] = mapped_column(String(64))
    # clock_timestamp(), not now(): now() is the transaction start, so several events in
    # one transaction would share a timestamp and lose their real order.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
