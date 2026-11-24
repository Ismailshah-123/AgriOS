"""Model registry (DATABASE_DESIGN model_versions + documented additions).

A row describes one immutable, evaluated model artefact. Being able to run a model does
NOT make it usable: only an admin-activated row whose artefact checksum verifies is used.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class ModelStatus(StrEnum):
    CANDIDATE = "candidate"
    ACTIVE = "active"
    RETIRED = "retired"


class ModelVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "model_versions"
    __table_args__ = (
        # At most one active model per task.
        Index(
            "uq_model_versions_active_task",
            "task",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    task: Mapped[str] = mapped_column(String(64))  # e.g. "crop_health_image"
    name: Mapped[str] = mapped_column(String(120))
    version: Mapped[str] = mapped_column(String(40))
    framework: Mapped[str] = mapped_column(String(40))  # e.g. "pytorch"
    arch: Mapped[str] = mapped_column(String(80))
    # Ordered output classes, each {"id", "label", "crop"}.
    labels: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    supported_crops: Mapped[list[str]] = mapped_column(JSONB)
    artifact_uri: Mapped[str] = mapped_column(String(255))  # relative to MODEL_PATH
    checksum_sha256: Mapped[str] = mapped_column(String(64))
    data_hash: Mapped[str | None] = mapped_column(String(64))
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    metrics_ref: Mapped[str | None] = mapped_column(String(255))  # saved evaluation run
    model_card_uri: Mapped[str | None] = mapped_column(String(255))
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    threshold: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))
    ood_threshold: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    status: Mapped[ModelStatus] = mapped_column(str_enum(ModelStatus, "model_status"))
    notes: Mapped[str | None] = mapped_column(Text)
