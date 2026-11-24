"""Liveness (/health) and readiness (/ready) probes."""

from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app import __version__
from app.api.deps import get_app_settings
from app.core.config import Settings
from app.db.session import Database, get_database

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    version: str
    environment: str


class ReadinessChecks(BaseModel):
    database: Literal["ok", "not_configured", "unavailable"]


class ReadinessResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: ReadinessChecks


def get_database_checker(
    db: Annotated[Database, Depends(get_database)],
) -> Callable[[], str]:
    return db.check


@router.get("/health", response_model=HealthResponse)
def health(settings: Annotated[Settings, Depends(get_app_settings)]) -> HealthResponse:
    """Process is up. Does not touch external dependencies."""
    return HealthResponse(
        status="ok", service="agrios-api", version=__version__, environment=settings.app_env
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
)
def ready(
    response: Response,
    check_db: Annotated[Callable[[], str], Depends(get_database_checker)],
) -> ReadinessResponse:
    """Dependencies reachable. Returns 503 when the database is not usable."""
    db_state = check_db()
    is_ready = db_state == "ok"
    if not is_ready:
        response.status_code = 503
    return ReadinessResponse(
        status="ready" if is_ready else "not_ready",
        checks=ReadinessChecks(database=db_state),  # type: ignore[arg-type]
    )
