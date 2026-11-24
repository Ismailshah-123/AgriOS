"""GET /weather?field_id= | ?farm_id= (API_CONTRACTS soil/weather group; owner only)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.identity.deps import CurrentUser, DbSession
from app.weather import service
from app.weather.provider import OpenMeteoProvider, WeatherProvider
from app.weather.schemas import WeatherOut

router = APIRouter(tags=["weather"])


def get_weather_provider(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> WeatherProvider | None:
    if settings.weather_provider == "disabled":
        return None
    return OpenMeteoProvider(settings.weather_base_url, settings.weather_timeout_s)


Provider = Annotated[WeatherProvider | None, Depends(get_weather_provider)]


@router.get("/weather", response_model=WeatherOut)
def get_weather(
    user: CurrentUser,
    db: DbSession,
    provider: Provider,
    settings: Annotated[Settings, Depends(get_app_settings)],
    field_id: uuid.UUID | None = None,
    farm_id: uuid.UUID | None = None,
) -> WeatherOut:
    return service.get_weather(
        db,
        user,
        provider,
        field_id=field_id,
        farm_id=farm_id,
        fresh_minutes=settings.weather_cache_minutes,
    )
