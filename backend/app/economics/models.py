"""Farm economics (FR10; DATABASE_DESIGN Economics): crop-cycle expenses and harvest/sales.

All money is Pakistani rupees (PKR) stored as NUMERIC(14, 2); quantities are kilograms.
Every row is farmer_entered. Maund is not offered until an official definition is recorded
(same rule as kanal/marla). Cycles with records cannot be deleted (RESTRICT + 409).
"""

import uuid
from datetime import date
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class ExpenseCategory(StrEnum):
    SEED = "seed"
    FERTILIZER = "fertilizer"
    PESTICIDE = "pesticide"
    LABOUR = "labour"
    MACHINERY = "machinery"
    IRRIGATION = "irrigation"
    ENERGY = "energy"
    LAND_RENT = "land_rent"
    TRANSPORT = "transport"
    OTHER = "other"


class Expense(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_cycle_date", "crop_cycle_id", "incurred_on"),
        CheckConstraint("amount_pkr > 0", name="amount_positive"),
    )

    crop_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_cycles.id", ondelete="RESTRICT")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    category: Mapped[ExpenseCategory] = mapped_column(str_enum(ExpenseCategory, "expense_category"))
    amount_pkr: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    incurred_on: Mapped[date] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(String(300))


class HarvestSale(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One harvest lot: quantity, and the sale price when it was sold (None = unsold)."""

    __tablename__ = "harvest_sales"
    __table_args__ = (
        Index("ix_harvest_sales_cycle_date", "crop_cycle_id", "recorded_on"),
        CheckConstraint("quantity_kg > 0", name="quantity_positive"),
        CheckConstraint(
            "price_pkr_per_kg IS NULL OR price_pkr_per_kg >= 0", name="price_non_negative"
        ),
    )

    crop_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_cycles.id", ondelete="RESTRICT")
    )
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    recorded_on: Mapped[date] = mapped_column(Date)
    quantity_kg: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    price_pkr_per_kg: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    buyer: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(String(300))
