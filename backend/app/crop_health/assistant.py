"""Crop Doctor AI assistant: explains a case in English or Urdu (FR3/FR8 support, not FR3 itself).

Roles are kept separate:
  * The DIAGNOSIS is only ever the registered, evaluated image model's decision (accepted /
    unsure / out_of_scope). The assistant cannot change or override it.
  * The vision LLM (Groq qwen by default) may DESCRIBE what is visible in the photo. That text is
    labelled "AI description of the photo (not verified)" and is never used as a diagnosis.
  * Disease facts and next steps must cite licence-verified passages [S#]; the case record
    (model result, farmer observations) is cited as [F]. Doses are removed (hard rule 2).
The photo leaves the server only when the farmer explicitly asks (send_photo=true).
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.crop_health.assistant_context import (
    CLASS_NAMES,
    DEFAULT_Q,
    SYSTEM,
    _parse,
    _photo,
    _record_block,
    case_record,
)
from app.crop_health.models import CaseImage, CropHealthCase
from app.knowledge import generation, retrieval
from app.knowledge.models import KnowledgeConversation, KnowledgeQuery
from app.knowledge.providers import LLMError, get_embedder, get_llm, get_vision_llm
from app.storage.base import Storage


def history(db: Session, user_id: uuid.UUID, case_id: uuid.UUID) -> list[KnowledgeQuery]:
    return list(
        db.scalars(
            select(KnowledgeQuery)
            .where(
                KnowledgeQuery.user_id == user_id,
                KnowledgeQuery.meta["case_id"].astext == str(case_id),
            )
            .order_by(KnowledgeQuery.created_at)
        )
    )


def ask(
    db: Session,
    settings: Settings,
    storage: Storage,
    user_id: uuid.UUID,
    case: CropHealthCase,
    question: str | None,
    language: str,
    send_photo: bool,
) -> KnowledgeQuery:
    t0 = time.perf_counter()
    lang = "ur" if language == "ur" else "en"
    q = " ".join((question or DEFAULT_Q[lang]).split())[:600]
    rec = case_record(db, case)
    m = rec["model_result"]
    accepted = m is not None and m["decision"] == "accepted"
    terms = CLASS_NAMES.get(m["predicted_class"] or "", ("", "", ""))[2] if accepted else ""
    if m and m["decision"] == "unsure":  # out_of_scope: retrieve from the farmer's symptoms only
        terms = " ".join(
            CLASS_NAMES.get(s["label"], ("", "", s["label"]))[2] for s in m["shortlist"]
        )
    symptoms = " ".join(" ".join(o["symptoms"]) for o in rec["observations"])
    rq = f"{terms} {symptoms} {q if lang == 'en' else ''}".strip() or "tomato leaf disease symptoms"
    tr = time.perf_counter()
    passages = retrieval.hybrid(db, rq, embedder=get_embedder(settings), dense_query=rq)
    retrieval_ms = int((time.perf_counter() - tr) * 1000)
    conv = db.scalar(
        select(KnowledgeConversation).where(
            KnowledgeConversation.user_id == user_id,
            KnowledgeConversation.title == f"Crop Doctor {rec['reference']}",
        )
    )
    if conv is None:
        conv = KnowledgeConversation(user_id=user_id, title=f"Crop Doctor {rec['reference']}")
        db.add(conv)
        db.flush()
    warnings: list[str] = []
    meta: dict[str, Any] = {
        "case_id": str(case.id),
        "kind": "crop_doctor_assistant",
        "case_record": rec,
        "photo_sent": False,
        "warnings": warnings,
        "retrieval_method": "hybrid (full-text + dense, RRF)",
    }
    row = KnowledgeQuery(
        user_id=user_id,
        conversation_id=conv.id,
        question=q,
        retrieval_query=rq[:2000],
        language=lang,
        domain="plant_protection",
        crops=["tomato"],
        citations=[],
        n_passages=len(passages),
    )
    vision = get_vision_llm(settings) if send_photo else None
    llm = vision or get_llm(settings)
    if send_photo and vision is None:
        warnings.append("vision_model_unavailable")
    parts = []
    for i, p in enumerate(passages, 1):
        s = p.source
        parts.append(
            f'<source id="S{i}" ref="{s["title"]}; {p.section or ""}">\n{p.text}\n</source>'
        )
    user_text = (
        "CASE RECORD (cite as [F]):\n"
        + _record_block(rec, lang)
        + "\n\nSOURCES:\n"
        + ("\n".join(parts) or "(none found)")
        + f"\n\nQUESTION: {q}"
    )
    content: Any = user_text
    if vision is not None:
        img = db.scalar(
            select(CaseImage)
            .where(CaseImage.case_id == case.id)
            .order_by(CaseImage.created_at.desc(), CaseImage.position)
        )
        if img is not None:
            content = [
                {"type": "text", "text": user_text},
                {"type": "image_url", "image_url": {"url": _photo(storage, img)}},
            ]
            meta["photo_sent"] = True
    if llm is None:
        row.status = "extractive" if passages else "abstained"
        row.answer = generation.extractive(rq, passages) if passages else None
        meta["sections"] = {"seen_in_photo": "", "explanation": row.answer or "", "next_steps": ""}
        warnings.append("llm_disabled")
    else:
        sysmsg = SYSTEM.format(language="Urdu (Urdu script)" if lang == "ur" else "English")
        try:
            r = llm.chat(
                [{"role": "system", "content": sysmsg}, {"role": "user", "content": content}],
                max_tokens=settings.llm_max_tokens,
                json_mode=False,
            )
            row.llm_provider, row.llm_model = r.provider, r.model
            row.prompt_tokens, row.completion_tokens = r.prompt_tokens, r.completion_tokens
            sec = _parse(r.text)
            checked = generation.validate(
                f"{sec['explanation']}\n\n{sec['next_steps']}",
                passages,
                has_farm=True,
                language=lang,
            )
            warnings += checked.warnings
            seen, _ = generation.redact_doses(sec["seen_in_photo"])
            expl, _ = generation.redact_doses(generation.normalise_citations(sec["explanation"]))
            steps, _ = generation.redact_doses(generation.normalise_citations(sec["next_steps"]))
            meta["sections"] = {"seen_in_photo": seen, "explanation": expl, "next_steps": steps}
            meta["grounded_share"] = checked.grounded_share
            row.status = "answered"
            row.answer = "\n\n".join(x for x in (seen, expl, steps) if x)
            row.citations = [_cite(i, p, i in checked.cited) for i, p in enumerate(passages, 1)]
        except LLMError as exc:
            warnings.append(f"llm_unavailable:{exc}")
            row.status = "extractive" if passages else "abstained"
            row.answer = generation.extractive(rq, passages) if passages else None
            row.citations = [_cite(i, p, i <= 3) for i, p in enumerate(passages, 1)]
            meta["sections"] = {
                "seen_in_photo": "",
                "explanation": row.answer or "",
                "next_steps": "",
            }
    if not accepted:
        warnings.append("no_validated_diagnosis_expert_review_advised")
    meta["warnings"] = sorted(set(warnings))
    meta["speech_text"] = generation.speech_text(row.answer or "")
    meta["evidence_quality"] = (
        "multiple_sources"
        if len({c["source_id"] for c in row.citations if c["cited"]}) > 1
        else "single_source"
    )
    row.meta = meta
    row.retrieval_ms = retrieval_ms
    row.total_ms = int((time.perf_counter() - t0) * 1000)
    conv.updated_at = datetime.now(UTC)
    db.add(row)
    db.flush()
    return row


def _cite(n: int, p: retrieval.Passage, cited: bool) -> dict[str, Any]:
    s = p.source
    text, _ = generation.redact_doses(p.text)
    return {
        "n": n,
        "marker": f"S{n}",
        "cited": cited,
        "chunk_id": str(p.chunk_id),
        "text": text,
        "page": p.page,
        "section": p.section,
        "source_id": str(s["id"]),
        "title": s["title"],
        "publisher": s["publisher"],
        "author": s["author"],
        "year": s["year"],
        "publication_date": s["publication_date"],
        "url": s["url"],
        "licence": s["licence"],
        "review_status": s["review_status"],
        "document_type": s["document_type"],
        "fts_rank": p.rank,
        "dense_score": p.dense,
        "matched_by": p.matched_by,
    }
