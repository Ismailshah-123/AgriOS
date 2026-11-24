"""Crop Doctor AI assistant endpoints (owner-only; 404 for anyone else)."""

from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.crop_health import assistant, queries
from app.crop_health.router import StorageDep
from app.identity.deps import AppSettings, CurrentUser, DbSession
from app.knowledge.models import KnowledgeQuery
from app.knowledge.router import AskOut, _limit

router = APIRouter(tags=["crop-doctor"])


class AssistantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str | None = Field(default=None, min_length=3, max_length=600)
    language: Literal["en", "ur"] = "en"
    send_photo: bool = False  # the photo goes to the external AI service only when true


@router.get("/cases/{case_id}/assistant", response_model=list[AskOut])
def assistant_history(case_id: uuid.UUID, user: CurrentUser, db: DbSession) -> list[KnowledgeQuery]:
    case = queries.get_owned_case(db, user.id, case_id)
    return assistant.history(db, user.id, case.id)


@router.post("/cases/{case_id}/assistant", response_model=AskOut)
def ask_assistant(
    case_id: uuid.UUID,
    body: AssistantIn,
    request: Request,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
    storage: StorageDep,
) -> KnowledgeQuery:
    case = queries.get_owned_case(db, user.id, case_id)
    _limit(request, user.id, settings.knowledge_ask_limit_per_minute)
    row = assistant.ask(
        db, settings, storage, user.id, case, body.question, body.language, body.send_photo
    )
    db.commit()
    return row
