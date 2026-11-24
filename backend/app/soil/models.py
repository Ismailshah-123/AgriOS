"""Soil observations (DATABASE_DESIGN: soil_observations). One row = one soil test of a
field on a date. Every value keeps its method; origin distinguishes laboratory results
(measured) from field-kit / manual readings (farmer_entered)."""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum
from app.kernel.origin import DataOrigin


class PhMethod(StrEnum):
    WATER_1_1 = "water_1_1"
    WATER_1_2_5 = "water_1_2_5"
    SATURATED_PASTE = "saturated_paste"
    CACL2 = "cacl2"
    UNKNOWN = "unknown"


class EcMethod(StrEnum):
    SATURATED_PASTE_ECE = "saturated_paste_ece"
    EXTRACT_1_1 = "extract_1_1"
    EXTRACT_1_2_5 = "extract_1_2_5"
    EXTRACT_1_5 = "extract_1_5"
    UNKNOWN = "unknown"


class PMethod(StrEnum):
    OLSEN = "olsen"
    BRAY_1 = "bray_1"
    MEHLICH_3 = "mehlich_3"
    UNKNOWN = "unknown"


class Texture(StrEnum):  # USDA texture classes
    SAND = "sand"
    LOAMY_SAND = "loamy_sand"
    SANDY_LOAM = "sandy_loam"
    LOAM = "loam"
    SILT_LOAM = "silt_loam"
    SILT = "silt"
    SANDY_CLAY_LOAM = "sandy_clay_loam"
    CLAY_LOAM = "clay_loam"
    SILTY_CLAY_LOAM = "silty_clay_loam"
    SANDY_CLAY = "sandy_clay"
    SILTY_CLAY = "silty_clay"
    CLAY = "clay"


class SoilObservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "soil_observations"
    __table_args__ = (
        Index("ix_soil_observations_field_date", "field_id", "sampled_on"),
        CheckConstraint("ph IS NULL OR (ph >= 0 AND ph <= 14)", name="ph_range"),
        CheckConstraint("ec_ds_m IS NULL OR (ec_ds_m >= 0 AND ec_ds_m <= 200)", name="ec_range"),
        CheckConstraint(
            "organic_matter_pct IS NULL OR (organic_matter_pct >= 0 AND organic_matter_pct <= 100)",
            name="om_range",
        ),
        CheckConstraint(
            "organic_carbon_pct IS NULL OR (organic_carbon_pct >= 0 AND organic_carbon_pct <= 60)",
            name="oc_range",
        ),
        CheckConstraint("data_origin IN ('measured', 'farmer_entered')", name="origin_allowed"),
    )

    field_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fields.id", ondelete="RESTRICT"), index=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    sampled_on: Mapped[date] = mapped_column(Date)
    data_origin: Mapped[DataOrigin] = mapped_column(str_enum(DataOrigin, "data_origin"))
    lab_name: Mapped[str | None] = mapped_column(String(120))
    lab_reference: Mapped[str | None] = mapped_column(String(80))
    depth_from_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    depth_to_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))
    ph: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    ph_method: Mapped[PhMethod] = mapped_column(str_enum(PhMethod, "soil_ph_method"))
    ec_ds_m: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    ec_method: Mapped[EcMethod] = mapped_column(str_enum(EcMethod, "soil_ec_method"))
    organic_matter_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    organic_carbon_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    nitrogen_total_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))
    phosphorus_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    phosphorus_method: Mapped[PMethod] = mapped_column(str_enum(PMethod, "soil_p_method"))
    potassium_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    calcium_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    magnesium_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    sulfur_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    zinc_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    iron_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    boron_mg_kg: Mapped[Decimal | None] = mapped_column(Numeric(7, 3))
    cec_cmol_kg: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    nutrient_methods: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    texture: Mapped[Texture | None] = mapped_column(str_enum(Texture, "soil_texture"))
    notes: Mapped[str | None] = mapped_column(Text)
