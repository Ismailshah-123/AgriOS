"""Farm domain: the spine every other module attaches to.

    users 1─N farms 1─N fields 1─N crop_cycles N─1 crop_definitions

Deletes are RESTRICTED down the chain (a farm with fields, or a field with crop
cycles, cannot be deleted) so history is never removed by cascade. Future modules
(soil, weather, irrigation, nutrients, economics, crop doctor) reference
`fields.id` or `crop_cycles.id`.
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum
from app.kernel.origin import DataOrigin
from app.units.area import AreaUnit


class Province(StrEnum):
    PUNJAB = "punjab"
    SINDH = "sindh"
    KHYBER_PAKHTUNKHWA = "khyber_pakhtunkhwa"
    BALOCHISTAN = "balochistan"
    GILGIT_BALTISTAN = "gilgit_baltistan"
    AZAD_JAMMU_KASHMIR = "azad_jammu_kashmir"
    ISLAMABAD = "islamabad_capital_territory"


class Season(StrEnum):
    KHARIF = "kharif"
    RABI = "rabi"
    OTHER = "other"


class CycleStatus(StrEnum):
    PLANNED = "planned"
    ACTIVE = "active"
    HARVESTED = "harvested"
    ABANDONED = "abandoned"


class Farm(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "farms"
    __table_args__ = (
        Index("uq_farms_owner_name", "owner_id", text("lower(name)"), unique=True),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name="location_both_or_neither"
        ),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    province: Mapped[Province | None] = mapped_column(str_enum(Province, "farm_province"))
    district: Mapped[str | None] = mapped_column(String(80))
    # Coarse location only (rounded to 0.01°, about 1 km) for privacy.
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    notes: Mapped[str | None] = mapped_column(Text)


class Field(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fields"
    __table_args__ = (
        Index("uq_fields_farm_name", "farm_id", text("lower(name)"), unique=True),
        CheckConstraint("area_ha > 0", name="area_positive"),
    )

    farm_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("farms.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    area_ha: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    # What the farmer typed, so the UI can show it back exactly.
    area_input_value: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    area_input_unit: Mapped[AreaUnit] = mapped_column(str_enum(AreaUnit, "area_unit"))
    area_origin: Mapped[DataOrigin] = mapped_column(str_enum(DataOrigin, "data_origin"))
    notes: Mapped[str | None] = mapped_column(Text)


class CropDefinition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Crop registry. Names only; agronomic parameters (Kc, stage lengths, nutrient
    needs) live in cited reference tables added by later modules."""

    __tablename__ = "crop_definitions"

    code: Mapped[str] = mapped_column(String(40), unique=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_ur: Mapped[str | None] = mapped_column(String(80))
    scientific_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class CropCycle(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "crop_cycles"
    __table_args__ = (
        Index("ix_crop_cycles_field_status", "field_id", "status"),
        CheckConstraint(
            "harvest_date IS NULL OR sowing_date IS NULL OR harvest_date >= sowing_date",
            name="harvest_after_sowing",
        ),
        CheckConstraint(
            "expected_harvest_date IS NULL OR sowing_date IS NULL "
            "OR expected_harvest_date >= sowing_date",
            name="expected_harvest_after_sowing",
        ),
        CheckConstraint("status <> 'active' OR sowing_date IS NOT NULL", name="active_sown"),
        CheckConstraint("status <> 'harvested' OR harvest_date IS NOT NULL", name="harvest_dated"),
        CheckConstraint("area_ha IS NULL OR area_ha > 0", name="area_positive"),
    )

    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fields.id", ondelete="RESTRICT"), index=True
    )
    crop_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_definitions.id", ondelete="RESTRICT"), index=True
    )
    variety: Mapped[str | None] = mapped_column(String(120))
    season: Mapped[Season | None] = mapped_column(str_enum(Season, "crop_season"))
    status: Mapped[CycleStatus] = mapped_column(str_enum(CycleStatus, "cycle_status"))
    sowing_date: Mapped[date | None] = mapped_column(Date)
    expected_harvest_date: Mapped[date | None] = mapped_column(Date)
    harvest_date: Mapped[date | None] = mapped_column(Date)
    # Planted area when only part of the field is used; NULL = whole field.
    area_ha: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    notes: Mapped[str | None] = mapped_column(Text)
