"""Class activation maps for a completed Crop Doctor analysis (FR4).

The predictor stores one normalised CAM grid per analysed image. The grid covers only
the model's centre crop (Resize(short side) + CenterCrop), so each map is returned with
`crop_box`: the crop's [left, top, width, height] as fractions of the stored image.
Never returned for out_of_scope decisions (the model's class is not meaningful there).
"""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crop_health import focus
from app.crop_health.models import (
    CaseImage,
    CaseStatus,
    CropHealthAnalysis,
    CropHealthCase,
    InferenceStatus,
)
from app.crop_health.queries import LIMITS_NOTE, Linker
from app.crop_health.schemas import ExplanationMap, ExplanationOut
from app.mlops.models import ModelVersion


def crop_box(width: int, height: int, prep: dict[str, Any]) -> list[float]:
    """Same geometry as app.mlops.onnx_predictor.preprocess, in fractions of the image."""
    short, crop = int(prep["resize_short_side"]), int(prep["center_crop"])
    if width <= height:
        nw, nh = short, int(short * height / width)
    else:
        nw, nh = int(short * width / height), short
    left, top = int(round((nw - crop) / 2.0)), int(round((nh - crop) / 2.0))
    return [round(left / nw, 4), round(top / nh, 4), round(crop / nw, 4), round(crop / nh, 4)]


def _unavailable(reason: str) -> ExplanationOut:
    return ExplanationOut(available=False, reason=reason, limits_note=LIMITS_NOTE)


def for_case(db: Session, case: CropHealthCase, link: Linker) -> ExplanationOut:
    if case.inference_status != InferenceStatus.COMPLETED:
        return _unavailable("no_completed_analysis")
    row = db.execute(
        select(CropHealthAnalysis, ModelVersion)
        .join(ModelVersion, ModelVersion.id == CropHealthAnalysis.model_version_id)
        .where(CropHealthAnalysis.case_id == case.id)
        .order_by(CropHealthAnalysis.created_at.desc())
        .limit(1)
    ).first()
    if row is None:
        return _unavailable("no_completed_analysis")
    a, mv = row
    if a.decision == CaseStatus.OUT_OF_SCOPE:
        return _unavailable("out_of_scope")
    exp = a.explanation or {}
    prep = (mv.config or {}).get("preprocessing")
    if not exp.get("maps") or not prep:
        return _unavailable("not_provided_by_model")
    ids = [uuid.UUID(i) for i in a.image_ids]
    images = {i.id: i for i in db.scalars(select(CaseImage).where(CaseImage.id.in_(ids)))}
    maps = []
    for m in exp["maps"]:
        idx = int(m["image_index"])
        img = images.get(ids[idx]) if 0 <= idx < len(ids) else None
        if img is None:  # photo removed since analysis: skip rather than mis-align
            continue
        maps.append(
            ExplanationMap(
                image=link.image(img),
                grid=m["grid"],
                crop_box=crop_box(img.width, img.height, prep),
                focus=focus.summarise(m["grid"]),
            )
        )
    if not maps:
        return _unavailable("not_provided_by_model")
    return ExplanationOut(
        available=True,
        method=str(exp.get("method", "class_activation_map")),
        target_class=exp.get("target_class"),
        decision=a.decision,
        note=str(exp.get("note", "")),
        maps=maps,
        model_name=mv.name,
        model_version=mv.version,
        limits_note=LIMITS_NOTE,
    )
