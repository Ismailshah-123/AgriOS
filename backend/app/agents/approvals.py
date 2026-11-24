"""Approval workflow for agent-proposed writes (hard rule 9).

pending -> approved -> executed | failed        (owner approves before expires_at)
pending -> rejected                             (owner rejects)
pending -> expired                              (lazily, once expires_at has passed)
Requester, approver and executor are stored; every transition writes an audit event.
Execution re-validates the input and re-checks ownership inside the service.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update

from app.agents import registry
from app.agents.models import ActionStatus, AgentAction
from app.agents.registry import ToolContext, ToolError
from app.audit import service as audit
from app.core.errors import AppError


def _audit(ctx: ToolContext, a: AgentAction, action: str, **meta: object) -> None:
    audit.record(
        ctx.db,
        action=f"agent_action.{action}",
        entity="agent_action",
        entity_id=a.id,
        actor_id=ctx.user.id,
        request_id=ctx.request_id,
        meta={"tool": a.tool, **meta},
    )


def expire_due(ctx: ToolContext, now: datetime | None = None) -> int:
    now = now or datetime.now(UTC)
    due = list(
        ctx.db.scalars(
            select(AgentAction).where(
                AgentAction.user_id == ctx.user.id,
                AgentAction.status == ActionStatus.PENDING,
                AgentAction.expires_at <= now,
            )
        )
    )
    for a in due:
        a.status = ActionStatus.EXPIRED
        _audit(ctx, a, "expired")
    if due:
        ctx.db.commit()
    return len(due)


def list_actions(ctx: ToolContext, status: ActionStatus | None) -> list[AgentAction]:
    expire_due(ctx)
    q = select(AgentAction).where(AgentAction.user_id == ctx.user.id)
    if status is not None:
        q = q.where(AgentAction.status == status)
    return list(ctx.db.scalars(q.order_by(AgentAction.created_at.desc()).limit(100)))


def _owned_pending(ctx: ToolContext, action_id: uuid.UUID, now: datetime) -> AgentAction:
    a = ctx.db.scalar(
        select(AgentAction).where(AgentAction.id == action_id, AgentAction.user_id == ctx.user.id)
    )
    if a is None:
        raise AppError("not_found", "Action not found.", 404)
    if a.status == ActionStatus.PENDING and a.expires_at <= now:
        a.status = ActionStatus.EXPIRED
        _audit(ctx, a, "expired")
        ctx.db.commit()
    if a.status != ActionStatus.PENDING:
        raise AppError("conflict", f"Action is {a.status}, not pending.", 409)
    return a


def approve(ctx: ToolContext, action_id: uuid.UUID, now: datetime | None = None) -> AgentAction:
    now = now or datetime.now(UTC)
    a = _owned_pending(ctx, action_id, now)
    # Claim atomically so a double click cannot execute twice.
    claimed = ctx.db.execute(
        update(AgentAction)
        .where(AgentAction.id == a.id, AgentAction.status == ActionStatus.PENDING)
        .values(status=ActionStatus.APPROVED, decided_by=ctx.user.id, decided_at=now)
    ).rowcount
    if claimed != 1:
        ctx.db.rollback()
        raise AppError("conflict", "Action was already decided.", 409)
    ctx.db.refresh(a)
    _audit(ctx, a, "approved")
    ctx.db.commit()
    action_id_, tool, args = a.id, a.tool, dict(a.args)
    try:
        res = registry.execute(ctx, tool, args, approved=True)
    except ToolError as e:
        ctx.db.rollback()
        a = ctx.db.get(AgentAction, action_id_)  # type: ignore[assignment]
        a.status, a.error_code = ActionStatus.FAILED, e.code[:64]
        _audit(ctx, a, "failed", error=e.code)
        ctx.db.commit()
        return a
    a = ctx.db.get(AgentAction, action_id_)  # type: ignore[assignment]
    a.status = ActionStatus.EXECUTED
    a.executed_by, a.executed_at = ctx.user.id, datetime.now(UTC)
    a.result = {"summary": res.summary, **res.data}
    _audit(ctx, a, "executed")
    ctx.db.commit()
    return a


def reject(ctx: ToolContext, action_id: uuid.UUID, now: datetime | None = None) -> AgentAction:
    now = now or datetime.now(UTC)
    a = _owned_pending(ctx, action_id, now)
    a.status, a.decided_by, a.decided_at = ActionStatus.REJECTED, ctx.user.id, now
    _audit(ctx, a, "rejected")
    ctx.db.commit()
    return a
