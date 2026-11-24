import uuid
from datetime import date, datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, StringConstraints, field_validator

from app.crop_health.models import (
    CaseStatus,
    InferenceStatus,
    PlantPart,
    ReviewDecision,
    SubmissionKind,
    Symptom,
)

Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)]
ClientId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
ModelAvailability = Literal[
    "not_registered", "not_installed", "checksum_mismatch", "loading", "ready", "error"
]


class SubmissionIn(BaseModel):
    """Farmer observations. Recorded as reported; never interpreted as a diagnosis."""

    plant_part: PlantPart | None = None
    symptoms: list[Symptom] = Field(default_factory=list, max_length=10)
    observed_on: date | None = None
    notes: Notes | None = None

    @field_validator("symptoms")
    @classmethod
    def _unique(cls, v: list[Symptom]) -> list[Symptom]:
        return list(dict.fromkeys(v))

    @field_validator("notes")
    @classmethod
    def _blank_to_none(cls, v: str | None) -> str | None:
        return v or None

    def is_empty(self) -> bool:
        return not (self.plant_part or self.symptoms or self.observed_on or self.notes)


# ------------------------------------------------------------------------ output


class ImageOut(BaseModel):
    id: uuid.UUID
    position: int
    width: int
    height: int
    url: str
    thumb_url: str
    urls_expire_at: datetime


class SubmissionOut(BaseModel):
    id: uuid.UUID
    kind: SubmissionKind
    plant_part: PlantPart | None
    symptoms: list[Symptom]
    observed_on: date | None
    notes: str | None
    submitted_at: datetime
    images: list[ImageOut]


class Ref(BaseModel):
    id: uuid.UUID
    name: str


class CropRef(BaseModel):
    id: uuid.UUID
    code: str
    name: str


class PredictionOut(BaseModel):
    decision: CaseStatus  # accepted | unsure | out_of_scope
    predicted_class: str | None  # only when decision == accepted
    calibrated_confidence: float
    ood_score: float | None
    shortlist: list[dict[str, float | str]]
    model_name: str
    model_version: str
    analysed_at: datetime
    image_count: int
    explanation_available: bool
    limits_note: str


class ExplanationMap(BaseModel):
    image: ImageOut
    grid: list[list[float]]  # rows x cols, normalised 0..1 (1 = strongest for target_class)
    crop_box: list[float]  # [left, top, width, height] of the model's crop, image fractions
    focus: dict[str, Any] | None = None  # plain-language summary of where the map is strong


class ExplanationOut(BaseModel):
    available: bool
    reason: Literal["no_completed_analysis", "out_of_scope", "not_provided_by_model"] | None = None
    method: str | None = None
    target_class: str | None = None
    decision: CaseStatus | None = None
    note: str | None = None
    maps: list[ExplanationMap] = []
    model_name: str | None = None
    model_version: str | None = None
    limits_note: str


class AnalysisOut(BaseModel):
    inference_status: InferenceStatus
    model_availability: ModelAvailability
    error_code: str | None
    message: str
    can_retry: bool
    result: PredictionOut | None


class TimelineEvent(BaseModel):
    at: datetime
    kind: Literal["created", "follow_up", "analysis_completed", "analysis_status"]
    text: str


class CaseListItem(BaseModel):
    id: uuid.UUID
    reference: str
    status: CaseStatus
    inference_status: InferenceStatus
    crop: CropRef
    farm: Ref
    field: Ref
    crop_cycle_id: uuid.UUID
    image_count: int
    submission_count: int
    thumb_url: str | None
    created_at: datetime
    last_activity_at: datetime


class ReviewOut(BaseModel):
    """FR12 expert outcome: human judgement, shown apart from model output."""

    id: uuid.UUID
    decision: ReviewDecision
    label: str | None
    note: str | None
    expert_name: str
    reviewed_at: datetime
    source: Literal["expert_review"] = "expert_review"


class CaseDetail(CaseListItem):
    consent_training: bool
    submissions: list[SubmissionOut]
    analysis: AnalysisOut
    timeline: list[TimelineEvent]
    expert_reviews: list[ReviewOut] = []


class CaseStats(BaseModel):
    total: int
    awaiting_analysis: int
    needs_follow_up: int
    by_inference_status: dict[InferenceStatus, int]
    model_availability: ModelAvailability
