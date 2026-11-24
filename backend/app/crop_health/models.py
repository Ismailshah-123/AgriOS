"""Crop Doctor domain (DATABASE_DESIGN "Doctor" group, adapted for multiple images).

    users 1â”€N diagnosis_cases Nâ”€1 crop_cycles            (owner + validated cycle)
    diagnosis_cases 1â”€N case_submissions 1â”€N case_images (initial + follow-ups)
    diagnosis_cases 1â”€N diagnosis_predictions Nâ”€1 model_versions

Three statuses stay separate (MODULE_CONTRACTS section 2):
  * status            -> documented case_status enum (unchanged)
  * inference_status  -> the analysis workflow for this case
  * model availability -> a system property, never stored per case
A prediction row exists ONLY after a successful inference by a registered model.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import str_enum


class CaseStatus(StrEnum):  # DATABASE_DESIGN.md case_status â€” do not change
    SUBMITTED = "submitted"
    RETAKE = "retake"
    UNSURE = "unsure"
    ACCEPTED = "accepted"
    OUT_OF_SCOPE = "out_of_scope"
    EXPERT_REVIEW = "expert_review"
    CLOSED = "closed"


class InferenceStatus(StrEnum):
    NOT_STARTED = "not_started"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MODEL_UNAVAILABLE = "model_unavailable"


class SubmissionKind(StrEnum):
    INITIAL = "initial"
    FOLLOW_UP = "follow_up"


class PlantPart(StrEnum):
    LEAF = "leaf"
    STEM = "stem"
    FRUIT = "fruit"
    FLOWER = "flower"
    ROOT = "root"
    WHOLE_PLANT = "whole_plant"
    OTHER = "other"


class Symptom(StrEnum):
    """Farmer-reported observations. Never treated as a diagnosis."""

    SPOTS = "spots"
    YELLOWING = "yellowing"
    WILTING = "wilting"
    CURLING = "curling"
    HOLES = "holes"
    MOULD = "mould"
    ROT = "rot"
    STUNTING = "stunting"
    INSECTS_SEEN = "insects_seen"
    OTHER = "other"


class CropHealthCase(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "diagnosis_cases"
    __table_args__ = (
        UniqueConstraint("owner_id", "number", name="uq_diagnosis_cases_owner_number"),
        UniqueConstraint("owner_id", "client_id", name="uq_diagnosis_cases_owner_client"),
        Index("ix_diagnosis_cases_owner_created", "owner_id", "created_at"),
        Index("ix_diagnosis_cases_cycle_status", "crop_cycle_id", "status"),
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    crop_cycle_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crop_cycles.id", ondelete="RESTRICT")
    )
    number: Mapped[int] = mapped_column(Integer)  # per-owner sequence -> "CD-000001"
    status: Mapped[CaseStatus] = mapped_column(str_enum(CaseStatus, "case_status"))
    inference_status: Mapped[InferenceStatus] = mapped_column(
        str_enum(InferenceStatus, "inference_status")
    )
    inference_error_code: Mapped[str | None] = mapped_column(String(64))
    # DATA_GOVERNANCE: images are never used for training without recorded consent.
    consent_training: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    client_id: Mapped[str | None] = mapped_column(String(64))  # offline idempotency
    last_activity_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CaseSubmission(UUIDPrimaryKeyMixin, Base):
    """Append-only: the initial report and each follow-up keep their own record."""

    __tablename__ = "case_submissions"
    __table_args__ = (Index("ix_case_submissions_case", "case_id", "submitted_at"),)

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("diagnosis_cases.id", ondelete="CASCADE"))
    kind: Mapped[SubmissionKind] = mapped_column(str_enum(SubmissionKind, "submission_kind"))
    plant_part: Mapped[PlantPart | None] = mapped_column(str_enum(PlantPart, "plant_part"))
    symptoms: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list)
    observed_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CaseImage(UUIDPrimaryKeyMixin, Base):
    """Processed derivatives only (EXIF/GPS removed). Originals are not stored."""

    __tablename__ = "case_images"
    __table_args__ = (
        Index("ix_case_images_case", "case_id"),
        CheckConstraint("width > 0 AND height > 0", name="positive_dimensions"),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("diagnosis_cases.id", ondelete="CASCADE"))
    submission_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("case_submissions.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(160), unique=True)
    thumb_key: Mapped[str] = mapped_column(String(160), unique=True)
    content_type: Mapped[str] = mapped_column(String(32))
    original_format: Mapped[str] = mapped_column(String(8))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    byte_size: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CropHealthAnalysis(UUIDPrimaryKeyMixin, Base):
    """A completed model inference. Never created without a registered model version."""

    __tablename__ = "diagnosis_predictions"
    __table_args__ = (Index("ix_diagnosis_predictions_case", "case_id", "created_at"),)

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("diagnosis_cases.id", ondelete="CASCADE"))
    model_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_versions.id", ondelete="RESTRICT")
    )
    decision: Mapped[CaseStatus] = mapped_column(str_enum(CaseStatus, "prediction_decision"))
    predicted_class: Mapped[str | None] = mapped_column(String(80))  # None when not accepted
    calibrated_conf: Mapped[Decimal] = mapped_column(Numeric(6, 5))
    ood_score: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    probs: Mapped[dict[str, float]] = mapped_column(JSONB)
    shortlist: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    image_ids: Mapped[list[str]] = mapped_column(JSONB)
    explanation: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # e.g. Grad-CAM keys
    context_used: Mapped[str] = mapped_column(String(16), default="none")
    duration_ms: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewDecision(StrEnum):
    CONFIRMED_MODEL = "confirmed_model"  # agrees with the model's accepted class
    DIAGNOSED = "diagnosed"  # expert's own label (model unsure, wrong or unavailable)
    NEEDS_RETAKE = "needs_retake"  # photos insufficient: case goes back to the farmer
    CANNOT_DETERMINE = "cannot_determine"
    NOT_SUPPORTED = "not_supported"  # outside supported crops/problems


class ExpertReview(UUIDPrimaryKeyMixin, Base):
    """FR12 expert outcome for a case (DATABASE_DESIGN expert_reviews). Append-only history:
    a new review adds a row; earlier rows are never edited. Human judgement, not model output."""

    __tablename__ = "expert_reviews"
    __table_args__ = (
        Index("ix_expert_reviews_case", "case_id", "created_at"),
        CheckConstraint(
            "decision NOT IN ('confirmed_model', 'diagnosed') OR label IS NOT NULL",
            name="label_required",
        ),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("diagnosis_cases.id", ondelete="CASCADE"))
    expert_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    decision: Mapped[ReviewDecision] = mapped_column(str_enum(ReviewDecision, "review_decision"))
    label: Mapped[str | None] = mapped_column(String(80))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
