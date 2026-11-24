"""Hybrid retrieval: PostgreSQL full-text (BM25-like ts_rank_cd) + dense cosine, fused with
Reciprocal Rank Fusion, then de-duplicated and cut to a context budget.

Only ACTIVE sources whose licence is verified are ever read (licence gate in every query).
Dense vectors live in knowledge_chunks.embedding (REAL[]); cosine is computed in numpy —
adequate for the FYP corpus (thousands of chunks). Scaling path: pgvector HNSW index.

Thresholds are PROVISIONAL (set by inspection on the development questions, never on the
evaluation questions): a passage counts as evidence only if its full-text rank >= MIN_RANK
or its cosine similarity >= DENSE_MIN. With no evidence the caller must abstain.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from sqlalchemy import Text, cast, func, or_, select
from sqlalchemy.orm import Session

from app.knowledge.models import SEARCHABLE, KnowledgeChunk, KnowledgeSource
from app.knowledge.providers import Embedder

MIN_RANK = 0.05
DENSE_MIN = 0.50
DENSE_SOFT = 0.40  # with a strong full-text match (rank >= FTS_STRONG)
FTS_STRONG = 0.30
CANDIDATES = 24
RRF_K = 60
MAX_PASSAGES = 5
MAX_CONTEXT_WORDS = 1100


@dataclass
class Filters:
    domain: str | None = None
    crop: str | None = None
    source_id: uuid.UUID | None = None
    document_type: str | None = None


@dataclass
class Passage:
    chunk_id: uuid.UUID
    text: str
    page: int | None
    section: str | None
    rank: float  # full-text rank (0 when matched by the dense retriever only)
    source: dict[str, Any]
    dense: float | None = None
    fused: float = 0.0
    evidence: bool = False
    matched_by: list[str] = field(default_factory=list)


def source_dict(s: KnowledgeSource) -> dict[str, Any]:
    return {
        "id": s.id,
        "title": s.title,
        "publisher": s.publisher,
        "author": s.author,
        "year": s.year,
        "publication_date": s.publication_date.isoformat() if s.publication_date else None,
        "url": s.url,
        "licence": s.licence,
        "review_status": s.review_status.value,
        "document_type": s.document_type,
        "domain": s.domain,
        "country": s.country,
        "language": s.language,
        "version": s.version,
    }


def _scope(stmt: Any, f: Filters) -> Any:
    stmt = stmt.where(
        KnowledgeSource.review_status.in_(SEARCHABLE), KnowledgeSource.is_active.is_(True)
    )
    if f.domain:
        stmt = stmt.where(KnowledgeSource.domain == f.domain)
    if f.document_type:
        stmt = stmt.where(KnowledgeSource.document_type == f.document_type)
    if f.source_id:
        stmt = stmt.where(KnowledgeSource.id == f.source_id)
    if f.crop:  # sources tagged with the crop, or general sources with no crop tag
        stmt = stmt.where(
            or_(KnowledgeSource.crops.any(f.crop), func.cardinality(KnowledgeSource.crops) == 0)
        )
    return stmt


def _fts(db: Session, q: str, f: Filters) -> list[tuple[KnowledgeChunk, KnowledgeSource, float]]:
    # Natural-language question: OR the stemmed terms; ts_rank_cd favours more matches.
    query = func.to_tsquery(
        "english", func.replace(cast(func.plainto_tsquery("english", q), Text), " & ", " | ")
    )
    rank = func.ts_rank_cd(KnowledgeChunk.tsv, query).label("rank")
    stmt = (
        select(KnowledgeChunk, KnowledgeSource, rank)
        .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
        .where(KnowledgeChunk.tsv.op("@@")(query))
    )
    rows = db.execute(_scope(stmt, f).order_by(rank.desc()).limit(CANDIDATES)).all()
    return [(c, s, float(r)) for c, s, r in rows]


def _dense(
    db: Session, q: str, f: Filters, embedder: Embedder
) -> tuple[list[tuple[uuid.UUID, float]], dict[uuid.UUID, float]]:
    """-> (top candidates by cosine, cosine for EVERY scanned chunk)."""
    stmt = (
        select(KnowledgeChunk.id, KnowledgeChunk.embedding)
        .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
        .where(
            KnowledgeChunk.embedding.is_not(None),
            KnowledgeChunk.embedding_model == embedder.model_name,
        )
    )
    rows = db.execute(_scope(stmt, f)).all()
    if not rows:
        return [], {}
    ids = [r[0] for r in rows]
    mat = np.asarray([r[1] for r in rows], dtype=np.float32)
    qv = embedder.embed([q])[0]
    sims = mat @ qv
    top = np.argsort(-sims)[:CANDIDATES]
    return [(ids[i], float(sims[i])) for i in top], dict(zip(ids, sims.tolist(), strict=True))


def _is_evidence(p: Passage, semantic: bool) -> bool:
    """Full-text alone (an OR of terms) lets one common word match, so when embeddings are
    available a passage must also be semantically close. FTS-only mode keeps MIN_RANK."""
    if not semantic or p.dense is None:
        return p.rank >= MIN_RANK
    return p.dense >= DENSE_MIN or (p.rank >= FTS_STRONG and p.dense >= DENSE_SOFT)


def _words(t: str) -> set[str]:
    return set(re.findall(r"\w{3,}", t.lower()))


def hybrid(
    db: Session,
    q: str,
    *,
    filters: Filters | None = None,
    embedder: Embedder | None = None,
    dense_query: str | None = None,
) -> list[Passage]:
    """Ranked, de-duplicated passages; each flagged `evidence` against the thresholds."""
    f = filters or Filters()
    by_id: dict[uuid.UUID, Passage] = {}
    fused: dict[uuid.UUID, float] = {}
    for i, (c, s, r) in enumerate(_fts(db, q, f)):
        by_id[c.id] = Passage(c.id, c.text, c.page, c.section, round(r, 4), source_dict(s))
        by_id[c.id].matched_by.append("full_text")
        fused[c.id] = 1 / (RRF_K + i + 1)
    if embedder is not None:
        dense, all_sims = _dense(db, dense_query or q, f, embedder)
        for cid, p in by_id.items():  # full-text hits also get their semantic score
            if cid in all_sims:
                p.dense = round(all_sims[cid], 4)
        missing = [cid for cid, _ in dense if cid not in by_id]
        if missing:
            for c, s in db.execute(
                select(KnowledgeChunk, KnowledgeSource)
                .join(KnowledgeSource, KnowledgeSource.id == KnowledgeChunk.source_id)
                .where(KnowledgeChunk.id.in_(missing))
            ).all():
                by_id[c.id] = Passage(c.id, c.text, c.page, c.section, 0.0, source_dict(s))
        for i, (cid, sim) in enumerate(dense):
            p = by_id[cid]
            p.dense = round(sim, 4)
            p.matched_by.append("dense")
            fused[cid] = fused.get(cid, 0.0) + 1 / (RRF_K + i + 1)
    ranked = sorted(by_id.values(), key=lambda p: -fused[p.chunk_id])
    out: list[Passage] = []
    seen: list[set[str]] = []
    words = 0
    for p in ranked:
        p.fused = round(fused[p.chunk_id], 5)
        p.evidence = _is_evidence(p, embedder is not None)
        if not p.evidence:
            continue
        w = _words(p.text)
        if any(len(w & o) / max(1, len(w | o)) > 0.7 for o in seen):
            continue  # near-duplicate (same text in two versions/sources)
        n = len(p.text.split())
        if out and words + n > MAX_CONTEXT_WORDS:
            break
        out.append(p)
        seen.append(w)
        words += n
        if len(out) >= MAX_PASSAGES:
            break
    return out
