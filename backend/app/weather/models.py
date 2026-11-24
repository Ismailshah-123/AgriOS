"""Cached provider responses. Keyed by provider + coarse location (0.01°), so one cache
row serves every farm at that location and contains no personal data."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import DateTime, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WeatherSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "weather_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "provider", "latitude", "longitude", name="uq_weather_snapshots_provider_location"
        ),
    )

    provider: Mapped[str] = mapped_column(String(40))
    latitude: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    longitude: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
