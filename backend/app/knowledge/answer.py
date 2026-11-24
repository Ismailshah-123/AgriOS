"""Ask pipeline: understand -> (rewrite) -> hybrid retrieve -> (farm records) -> generate or
quote -> validate -> persist telemetry. Every outcome is stored in knowledge_queries."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.knowledge import farm_context, generation, query, retrieval
from app.knowledge.models import KnowledgeConversation, KnowledgeQuery
from app.knowledge.providers import LLMError, get_embedder, get_llm

NO_GUIDANCE = {
    "en": "No verified guidance found. AgriOS answers only from reviewed, licensed sources, and "
    "none of them covers this question. Ask an agricultural expert or your extension office.",
    "ur": "تصدیق شدہ ذرائع میں اس سوال کا جواب نہیں ملا۔ AgriOS صرف جانچے گئے، لائسنس یافتہ "
    "ذرائع سے جواب دیتا ہے۔ براہِ کرم کسی زرعی ماہر یا محکمہ زراعت (توسیع) سے رابطہ کریں۔",
}
CLARIFY = {
    "en": "Could you add a little more detail - which crop, and what you are seeing or planning?",
    "ur": "براہِ کرم تھوڑی مزید تفصیل بتائیں - کون سی فصل، اور آپ کیا دیکھ رہے ہیں؟",
}
DOSE_REFUSAL = {
    "en": "AgriOS does not give pesticide, fungicide or fertilizer doses. Use the product "
    "label or a reviewed local recommendation, and confirm with an agricultural expert. "
    "General guidance from verified sources:",
    "ur": "AgriOS کیڑے مار، پھپھوندی کش دوا یا کھاد کی مقدار نہیں بتاتا۔ پروڈکٹ لیبل یا "
    "مقامی سفارشات دیکھیں اور کسی زرعی ماہر سے تصدیق کریں۔ تصدیق شدہ ذرائع سے عمومی رہنمائی:",
}
VET_NOTE = "Animal health: general information only - consult a veterinarian for diagnosis."


@dataclass
class AskInput:
    question: str
    conversation_id: uuid.UUID | None = None
    language: str = "auto"  # auto | en | ur
    filters: retrieval.Filters = field(default_factory=retrieval.Filters)
    farm_context: str = "auto"  # auto | on | off


def _conversation(
    db: Session, user_id: uuid.UUID, cid: uuid.UUID | None, q: str
) -> KnowledgeConversation:
    if cid is not None:
        conv = db.get(KnowledgeConversation, cid)
        if conv is None or conv.user_id != user_id:  # never reveal others' conversations
            raise AppError("not_found", "Conversation not found.", 404)
        return conv
    conv = KnowledgeConversation(user_id=user_id, title=q[:200])
    db.add(conv)
    db.flush()
    return conv


def _citation(n: int, p: retrieval.Passage, cited: bool) -> dict[str, Any]:
    s = p.source
    return {
        "n": n,
        "marker": f"S{n}",
        "cited": cited,
        "chunk_id": str(p.chunk_id),
        "text": p.text,
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


def _quality(cites: list[dict[str, Any]]) -> str:
    used = [c for c in cites if c["cited"]]
    if len(used) >= 2 and len({c["source_id"] for c in used}) >= 2:
        return "multiple_sources"
    if len(used) >= 2:
        return "single_source_multiple_passages"
    return "single_passage" if used else "none"


def ask(db: Session, settings: Settings, user_id: uuid.UUID, inp: AskInput) -> KnowledgeQuery:
    t0 = time.perf_counter()
    q = " ".join(inp.question.split())
    info = query.analyse(q)
    lang = info.language if inp.language == "auto" else inp.language
    out_lang = "ur" if lang.startswith("ur") else "en"
    conv = _conversation(db, user_id, inp.conversation_id, q)
    history = [
        (h.question, h.answer or "")
        for h in db.scalars(
            select(KnowledgeQuery)
            .where(KnowledgeQuery.conversation_id == conv.id)
            .order_by(KnowledgeQuery.created_at.desc())
            .limit(3)
        )
    ][::-1]
    llm = get_llm(settings)
    embedder = get_embedder(settings)
    warnings: list[str] = []
    meta: dict[str, Any] = {
        "language_detected": info.language,
        "domains": info.domains,
        "farm_intent": info.farm_intent,
        "parts": info.parts,
    }
    usage = [0, 0]
    rq, clarify = None, None
    if llm is not None and (history or info.language != "en"):
        try:
            r = llm.chat(generation.rewrite_messages(q, history), max_tokens=400, json_mode=True)
            rq, clarify = generation.parse_rewrite(r.text)
            usage[0] += r.prompt_tokens or 0
            usage[1] += r.completion_tokens or 0
        except LLMError as exc:
            warnings.append(f"rewrite_failed:{exc}")
    if rq is None:  # deterministic: carry the previous question's terms into a follow-up
        rq = f"{history[-1][0]} {info.retrieval_terms}" if history else info.retrieval_terms
    meta["retrieval_query"] = rq
    row = KnowledgeQuery(
        user_id=user_id,
        conversation_id=conv.id,
        question=q,
        retrieval_query=rq[:2000],
        language=lang,
        domain=(inp.filters.domain or (info.domains[0] if info.domains else None)),
        crops=info.crops,
        citations=[],
    )
    if not history and (clarify or query.is_ambiguous(q, info)):
        row.status, row.answer = "clarify", clarify or CLARIFY[out_lang]
        return _finish(db, conv, row, meta, warnings, t0, 0, llm, usage)

    tr = time.perf_counter()
    extra = " ".join(query.glossary_terms(q)) if info.language != "en" else ""
    passages = retrieval.hybrid(
        db, f"{rq} {extra}".strip(), filters=inp.filters, embedder=embedder, dense_query=rq
    )
    retrieval_ms = int((time.perf_counter() - tr) * 1000)
    meta["retrieval_method"] = "hybrid (full-text + dense, RRF)" if embedder else "full-text"
    if embedder is None and settings.embedding_provider != "none":
        warnings.append("embeddings_unavailable_fulltext_only")
    use_farm = inp.farm_context == "on" or (inp.farm_context == "auto" and info.farm_intent)
    farm = farm_context.collect(db, user_id) if use_farm else None
    meta["farm_context"] = farm
    if info.veterinary:
        warnings.append("veterinary_general_information_only")
    if info.dose_request:
        warnings.append("dose_request_refused_escalate_to_expert")
        meta["escalate_to_expert"] = True
    row.n_passages = len(passages)
    row.top_score = max((p.fused for p in passages), default=None)
    if not passages and farm is None:
        row.status, row.answer = "abstained", NO_GUIDANCE[out_lang]
        return _finish(db, conv, row, meta, warnings, t0, retrieval_ms, llm, usage)

    cites_all = passages
    if llm is not None:
        farm_block = farm_context.as_prompt_block(farm) if farm is not None else None
        try:
            r = llm.chat(
                generation.build_messages(q, passages, lang, farm_block),
                max_tokens=settings.llm_max_tokens,
            )
            usage[0] += r.prompt_tokens or 0
            usage[1] += r.completion_tokens or 0
            v = generation.validate(r.text, passages, has_farm=farm is not None, language=out_lang)
            warnings += v.warnings
            meta["grounded_share"] = v.grounded_share
            if v.abstained:
                row.status, row.answer = "abstained", NO_GUIDANCE[out_lang]
                meta["llm_abstained"] = True
            elif v.grounded_share is not None and v.grounded_share < 0.5:
                warnings.append("generated_answer_failed_grounding_check")
                meta["rejected_generation"] = v.text[:3000]  # kept for audit / evaluation
                row.status = "extractive"
                row.answer = generation.extractive(rq, passages) if passages else None
            else:
                row.status, row.answer = "answered", v.text
                row.citations = [_citation(i, p, i in v.cited) for i, p in enumerate(cites_all, 1)]
                meta["farm_cited"] = v.farm_cited
        except LLMError as exc:
            warnings.append(f"llm_unavailable:{exc}")
            row.status = "extractive"
    else:
        row.status = "extractive"
    if row.status == "extractive":
        if passages:
            row.answer = row.answer or generation.extractive(rq, passages)
            row.citations = [_citation(i, p, i <= 3) for i, p in enumerate(passages, 1)]
        else:  # farm records only, no LLM: the UI shows the structured records
            row.answer = "Your recorded farm data is shown below. No verified source passage "
            row.answer += "matched this question."
    if row.status == "abstained":
        row.citations = []
    if info.dose_request and row.answer and row.status in ("answered", "extractive"):
        row.answer = f"{DOSE_REFUSAL[out_lang]}\n\n{row.answer}"
    redacted = False
    for c in row.citations:
        c["text"], changed = generation.redact_doses(c["text"])
        redacted = redacted or changed
    if row.answer:
        row.answer, changed = generation.redact_doses(row.answer)
        redacted = redacted or changed
    if redacted:
        warnings.append("dose_removed")
    return _finish(db, conv, row, meta, warnings, t0, retrieval_ms, llm, usage)


def _finish(
    db: Session,
    conv: KnowledgeConversation,
    row: KnowledgeQuery,
    meta: dict[str, Any],
    warnings: list[str],
    t0: float,
    retrieval_ms: int,
    llm: Any,
    usage: list[int],
) -> KnowledgeQuery:
    if row.status == "clarify":
        row.citations = []
    meta["warnings"] = sorted(set(warnings))
    meta["evidence_quality"] = _quality(row.citations)
    meta["speech_text"] = generation.speech_text(row.answer or "")
    if meta.get("farm_context"):
        meta["farm_context"] = _jsonable(meta["farm_context"])
    row.meta = meta
    row.retrieval_ms = retrieval_ms
    row.total_ms = int((time.perf_counter() - t0) * 1000)
    if llm is not None and (usage[0] or usage[1]):
        row.llm_provider, row.llm_model = llm.provider, llm.model
        row.prompt_tokens, row.completion_tokens = usage
    conv.updated_at = datetime.now(UTC)
    db.add(row)
    db.flush()
    return row


def _jsonable(v: Any) -> Any:
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, uuid.UUID):
        return str(v)
    return v
