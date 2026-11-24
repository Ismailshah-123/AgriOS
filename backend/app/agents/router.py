"""Agent API (owner-scoped). POST runs; history; tool/agent catalogue; approvals."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.agents import approvals, orchestrator, registry
from app.agents.agents import AGENTS
from app.agents.models import ActionStatus, AgentAction, AgentRun, AgentStep
from app.agents.registry import ToolContext
from app.api.deps import get_app_settings
from app.core.config import Settings
from app.core.errors import AppError
from app.core.pagination import DEFAULT_LIMIT, Cursor, Limit, Page, paginate, to_page
from app.identity.deps import CurrentUser, DbSession, RequestId
from app.weather.router import Provider

router = APIRouter(prefix="/agent", tags=["agents"])
AppSettings = Annotated[Settings, Depends(get_app_settings)]


class RunIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=2, max_length=500)
    farm_id: uuid.UUID | None = None
    field_id: uuid.UUID | None = None


class StepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    position: int
    agent: str
    tool: str
    mode: str
    input: dict[str, Any]
    status: str
    summary: str | None
    error_code: str | None
    duration_ms: int


class ActionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    run_id: uuid.UUID
    agent: str
    tool: str
    args: dict[str, Any]
    description: str
    status: str
    requested_by: uuid.UUID
    decided_by: uuid.UUID | None
    decided_at: datetime | None
    executed_by: uuid.UUID | None
    executed_at: datetime | None
    expires_at: datetime
    result: dict[str, Any] | None
    error_code: str | None
    created_at: datetime


class RunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    message: str
    intent: str
    agents: list[str]
    status: str
    farm_id: uuid.UUID | None
    field_id: uuid.UUID | None
    duration_ms: int
    created_at: datetime


class RunOut(RunSummary):
    response: dict[str, Any]
    steps: list[StepOut]
    actions: list[ActionOut]


def _ctx(db: Any, user: Any, settings: Settings, provider: Any, rid: str | None) -> ToolContext:
    return ToolContext(db=db, user=user, settings=settings, weather=provider, request_id=rid)


def _run_out(db: Any, run: AgentRun) -> RunOut:
    steps = db.scalars(
        select(AgentStep).where(AgentStep.run_id == run.id).order_by(AgentStep.position)
    ).all()
    acts = db.scalars(select(AgentAction).where(AgentAction.run_id == run.id)).all()
    return RunOut(
        **RunSummary.model_validate(run).model_dump(),
        response=run.response,
        steps=[StepOut.model_validate(s) for s in steps],
        actions=[ActionOut.model_validate(a) for a in acts],
    )


@router.post("/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(
    body: RunIn,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    provider: Provider,
    rid: RequestId,
) -> RunOut:
    run = orchestrator.run(
        _ctx(db, user, settings, provider, rid), body.message.strip(), body.farm_id, body.field_id
    )
    return _run_out(db, run)


@router.get("/runs", response_model=Page[RunSummary])
def list_runs(
    user: CurrentUser, db: DbSession, limit: Limit = DEFAULT_LIMIT, cursor: Cursor = None
) -> Page[RunSummary]:
    stmt = select(AgentRun).where(AgentRun.user_id == user.id)
    rows = db.scalars(paginate(stmt, AgentRun, limit, cursor)).all()
    return to_page([RunSummary.model_validate(r) for r in rows], limit)


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID, user: CurrentUser, db: DbSession) -> RunOut:
    run = db.scalar(select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user.id))
    if run is None:
        raise AppError("not_found", "Run not found.", 404)
    return _run_out(db, run)


@router.get("/actions", response_model=list[ActionOut])
def list_actions(user: CurrentUser, db: DbSession, settings: AppSettings,
                 status_: Annotated[ActionStatus | None, Field(alias="status")] = None
                 ) -> list[ActionOut]:  # fmt: skip
    ctx = _ctx(db, user, settings, None, None)
    return [ActionOut.model_validate(a) for a in approvals.list_actions(ctx, status_)]


@router.post("/actions/{action_id}/approve", response_model=ActionOut)
def approve_action(
    action_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    provider: Provider,
    rid: RequestId,
) -> ActionOut:
    return ActionOut.model_validate(
        approvals.approve(_ctx(db, user, settings, provider, rid), action_id)
    )


@router.post("/actions/{action_id}/reject", response_model=ActionOut)
def reject_action(
    action_id: uuid.UUID, user: CurrentUser, db: DbSession, settings: AppSettings, rid: RequestId
) -> ActionOut:
    return ActionOut.model_validate(
        approvals.reject(_ctx(db, user, settings, None, rid), action_id)
    )


@router.get("/catalogue")
def catalogue(user: CurrentUser) -> dict[str, Any]:
    return {
        "agents": [a.describe() for a in AGENTS.values()],
        "tools": [t.describe() for t in registry.TOOLS.values()],
        "llm_used": False,
    }
