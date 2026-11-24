"""Weather for a farm or field the user owns: cache -> provider -> stale cache -> unavailable.
Readings are never invented; every response states its freshness and provider."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.farms import repository as farm_repo
from app.identity.models import User
from app.weather import indicators
from app.weather.models import WeatherSnapshot
from app.weather.provider import ProviderError, WeatherProvider
from app.weather.schemas import WeatherLocation, WeatherOut

log = logging.getLogger("agrios.weather")
HOURLY_POINTS = 72


def resolve_location(
    db: Session, user: User, field_id: uuid.UUID | None, farm_id: uuid.UUID | None
) -> tuple[WeatherLocation, Decimal | None, Decimal | None]:
    if (field_id is None) == (farm_id is None):
        raise AppError("validation_error", "Give exactly one of field_id or farm_id.", 422)
    fid = None
    if field_id is not None:
        row = farm_repo.get_field_row(db, user.id, field_id)
        if row is None:
            raise AppError("not_found", "Field not found.", 404)
        farm_id, fid = row[0].farm_id, str(field_id)
    farm = farm_repo.get_owned_farm(db, user.id, farm_id)  # type: ignore[arg-type]
    if farm is None:
        raise AppError("not_found", "Farm not found.", 404)
    loc = WeatherLocation(
        farm_id=str(farm.id),
        farm_name=farm.name,
        field_id=fid,
        latitude=float(farm.latitude) if farm.latitude is not None else None,
        longitude=float(farm.longitude) if farm.longitude is not None else None,
    )
    return loc, farm.latitude, farm.longitude


def _build(
    loc: WeatherLocation,
    status: str,
    snap: WeatherSnapshot,
    provider: dict[str, str],
    reason: str | None,
    now: datetime,
) -> WeatherOut:
    p: dict[str, Any] = snap.payload
    upcoming = [
        h for h in p.get("hourly", []) if h.get("time", "") >= (p["current"].get("time") or "")
    ][:HOURLY_POINTS]
    return WeatherOut(
        status=status,
        reason=reason,
        location=loc,
        provider=provider,  # type: ignore[arg-type]
        retrieved_at=snap.fetched_at,
        age_minutes=int((now - snap.fetched_at).total_seconds() // 60),
        timezone=p.get("timezone"),
        current=p.get("current"),
        hourly=upcoming,
        daily=p.get("daily", []),
        indicators=indicators.evaluate(p),
        not_evaluated=indicators.NOT_EVALUATED,
    )


def get_weather(
    db: Session,
    user: User,
    provider: WeatherProvider | None,
    *,
    field_id: uuid.UUID | None = None,
    farm_id: uuid.UUID | None = None,
    fresh_minutes: int = 30,
    max_stale_hours: int = 24,
    now: datetime | None = None,
) -> WeatherOut:
    now = now or datetime.now(UTC)
    loc, lat, lon = resolve_location(db, user, field_id, farm_id)
    if lat is None or lon is None:
        return WeatherOut(status="unavailable", reason="location_missing", location=loc)
    if provider is None:
        return WeatherOut(status="unavailable", reason="provider_disabled", location=loc)
    snap = db.scalar(
        select(WeatherSnapshot).where(
            WeatherSnapshot.provider == provider.name,
            WeatherSnapshot.latitude == lat,
            WeatherSnapshot.longitude == lon,
        )
    )
    if snap is not None and now - snap.fetched_at < timedelta(minutes=fresh_minutes):
        return _build(loc, "fresh", snap, provider.attribution, None, now)
    try:
        payload = provider.fetch(float(lat), float(lon))
    except ProviderError as e:
        log.warning("weather_provider_error", extra={"provider": provider.name, "error": str(e)})
        if snap is not None and now - snap.fetched_at < timedelta(hours=max_stale_hours):
            return _build(loc, "stale", snap, provider.attribution, "provider_error", now)
        return WeatherOut(
            status="unavailable",
            reason="provider_error",
            location=loc,
            provider=provider.attribution,
        )
    stmt = insert(WeatherSnapshot).values(
        id=uuid.uuid4(),
        provider=provider.name,
        latitude=lat,
        longitude=lon,
        fetched_at=now,
        payload=payload,
    )
    stmt = stmt.on_conflict_do_update(
        constraint="uq_weather_snapshots_provider_location",
        set_={"fetched_at": now, "payload": payload, "updated_at": now},
    )
    db.execute(stmt)
    db.commit()
    snap = db.scalar(
        select(WeatherSnapshot).where(
            WeatherSnapshot.provider == provider.name,
            WeatherSnapshot.latitude == lat,
            WeatherSnapshot.longitude == lon,
        )
    )
    db.refresh(snap)
    return _build(loc, "fresh", snap, provider.attribution, None, now)  # type: ignore[arg-type]
