"""FR6 fertilizer requirement for a crop cycle. With no reviewed table for the crop the
answer is an explicit refusal with expert escalation and NO numbers (hard rule 2)."""

import uuid
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import AppError
from app.farms import repository as farm_repo
from app.identity.deps import CurrentUser, DbSession
from app.nutrients.engine import REVIEWED_TABLES

router = APIRouter(tags=["nutrients"])


class FertilizerOut(BaseModel):
    crop_cycle_id: uuid.UUID
    crop_code: str
    status: Literal["refused"]
    reason: Literal["no_reviewed_source"]
    message: str
    escalation: Literal["expert_review"] = "expert_review"
    doses: None = None
    soil_test_note: str


@router.get("/crop-cycles/{cycle_id}/fertilizer", response_model=FertilizerOut)
def fertilizer(cycle_id: uuid.UUID, user: CurrentUser, db: DbSession) -> FertilizerOut:
    row = farm_repo.get_cycle_row(db, user.id, cycle_id)
    if row is None:
        raise AppError("not_found", "Crop cycle not found.", 404)
    crop = row[3]
    if crop.code in REVIEWED_TABLES:  # pragma: no cover - no reviewed table exists yet
        raise AppError("not_implemented", "Reviewed-table doses are not enabled yet.", 501)
    return FertilizerOut(
        crop_cycle_id=cycle_id,
        crop_code=crop.code,
        status="refused",
        reason="no_reviewed_source",
        message=(
            f"No reviewed, cited fertilizer requirement table is stored for {crop.name_en}. "
            "AgriOS does not estimate doses without one. Ask an agricultural expert or your "
            "local extension office; your soil test values can help them."
        ),
        soil_test_note="Soil tests are on the Soil page with cited pH and salinity flags only.",
    )
