"""Agent runs, their tool steps, and approval-gated action proposals.

agent_runs       one user request handled by the orchestrator (owner-scoped).
agent_steps      every tool call made during a run: tool, mode, input, status, timing.
agent_actions    a consequential (write) tool call the agent PROPOSED. It executes only
                 after the owner approves it before `expires_at`; requester, approver and
                 executor are recorded, and each transition writes an audit event.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class RunStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"  # some steps failed or data was unavailable
    FAILED = "failed"


class StepStatus(StrEnum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    ERROR = "error"
    TIMEOUT = "timeout"
    DENIED = "denied"
    PROPOSED = "proposed"  # write tool: became an action awaiting approval


class ActionStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"  # transient: approved and being executed
    REJECTED = "rejected"
    EXPIRED = "expired"
    EXECUTED = "executed"
    FAILED = "failed"


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (Index("ix_agent_runs_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    farm_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("farms.id", ondelete="SET NULL"))
    field_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("fields.id", ondelete="SET NULL"))
    message: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(String(40))
    agents: Mapped[list[str]] = mapped_column(JSONB)
    status: Mapped[RunStatus] = mapped_column(str_enum(RunStatus, "agent_run_status"))
    response: Mapped[dict[str, Any]] = mapped_column(JSONB)
    duration_ms: Mapped[int] = mapped_column(Integer)


class AgentStep(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_steps"

    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer)
    agent: Mapped[str] = mapped_column(String(40))
    tool: Mapped[str] = mapped_column(String(60))
    mode: Mapped[str] = mapped_column(String(8))  # read | write
    input: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[StepStatus] = mapped_column(str_enum(StepStatus, "agent_step_status"))
    summary: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int] = mapped_column(Integer)


class AgentAction(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_actions"
    __table_args__ = (Index("ix_agent_actions_user_status", "user_id", "status"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"))
    agent: Mapped[str] = mapped_column(String(40))
    tool: Mapped[str] = mapped_column(String(60))
    args: Mapped[dict[str, Any]] = mapped_column(JSONB)
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[ActionStatus] = mapped_column(str_enum(ActionStatus, "agent_action_status"))
    requested_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    executed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String(64))
