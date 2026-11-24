"""GET /fields/{field_id}/water-demand (owner only): estimated ETc for the forecast days."""

import uuid
from typing import Any

from fastapi import APIRouter

from app.identity.deps import CurrentUser, DbSession
from app.irrigation import service
from app.weather.router import Provider

router = APIRouter(tags=["irrigation"])


@router.get("/fields/{field_id}/water-demand")
def water_demand(
    field_id: uuid.UUID, user: CurrentUser, db: DbSession, provider: Provider
) -> dict[str, Any]:
    return service.water_demand(db, user, field_id, provider)
