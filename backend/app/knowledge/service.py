"""FR8 knowledge: chunking, licence-gated indexing, cited search.

`ingest` is the tested core used by the ingestion job (ingestion.py) and tests. It refuses
any source whose licence is not verified. Chunks keep page + section; each chunk gets a
content hash (duplicate detection) and, when an embedder is configured, a dense vector.
"""

from __future__ import annotations

import hashlib
import re

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.knowledge import retrieval
from app.knowledge.extract import detect_language
from app.knowledge.models import SEARCHABLE, KnowledgeChunk, KnowledgeSource
from app.knowledge.providers import Embedder
from app.knowledge.retrieval import Passage

MIN_RANK = retrieval.MIN_RANK  # kept for callers of the v1 API


class SourceNotVerified(ValueError):
    pass


def chunk(text: str, max_words: int = 220, overlap: int = 40) -> list[str]:
    """Paragraph-aware chunks of <= max_words with a word overlap between chunks."""
    words: list[str] = []
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text.strip()):
        pw = para.split()
        if words and len(words) + len(pw) > max_words:
            out.append(" ".join(words))
            words = words[-overlap:] if overlap else []
        words.extend(pw)
        while len(words) > max_words:
            out.append(" ".join(words[:max_words]))
            words = words[max_words - overlap :]
    if words:
        out.append(" ".join(words))
    return out


def chunk_sections(
    pages: list[tuple[int | None, str | None, str]], max_words: int = 220, overlap: int = 40
) -> list[tuple[int | None, str | None, str]]:
    """Section-aware: never merges text across a page or section boundary, so every chunk
    has exactly one page and one section reference. Tiny fragments (< 12 words) are merged
    into the next chunk of the same section only."""
    out: list[tuple[int | None, str | None, str]] = []
    for page, section, text in pages:
        for piece in chunk(text, max_words, overlap):
            if out and out[-1][:2] == (page, section) and len(out[-1][2].split()) < 12:
                out[-1] = (page, section, out[-1][2] + " " + piece)
            else:
                out.append((page, section, piece))
    return out


def _hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode()).hexdigest()


def ingest(
    db: Session,
    source: KnowledgeSource,
    pages: list[tuple[int | None, str | None, str]],
    *,
    embedder: Embedder | None = None,
    replace: bool = False,
) -> int:
    """pages = [(page_no, section, text)]. Returns the number of chunks written.

    replace=True swaps the source's chunks for the new ones in the caller's transaction
    (reprocessing / a new version): readers see either the old or the new set, never both.
    Chunks whose text already exists in this source are skipped (duplicate detection)."""
    if source.review_status not in SEARCHABLE:
        raise SourceNotVerified(f"source '{source.title}' is {source.review_status.value}")
    if replace:
        db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source.id))
        seen: set[str] = set()
        pos = 0
    else:
        seen = set(
            db.scalars(
                select(KnowledgeChunk.content_hash).where(KnowledgeChunk.source_id == source.id)
            )
        )
        n = db.scalar(
            select(func.coalesce(func.max(KnowledgeChunk.position), -1)).where(
                KnowledgeChunk.source_id == source.id
            )
        )
        pos = (n if n is not None else -1) + 1
    rows: list[KnowledgeChunk] = []
    for page, section, piece in chunk_sections(pages):
        h = _hash(piece)
        if h in seen:
            continue
        seen.add(h)
        rows.append(
            KnowledgeChunk(
                source_id=source.id,
                position=pos,
                page=page,
                section=section[:200] if section else None,
                text=piece,
                content_hash=h,
                language=detect_language(piece),
                source_version=source.version or 1,
            )
        )
        pos += 1
    if embedder is not None and rows:
        # Contextual header: document title + section, so a chunk is findable by what the
        # document is about even when its own text never names it (e.g. "early blight").
        texts = [f"{source.title} - {r.section or ''}\n{r.text}" for r in rows]
        for i in range(0, len(rows), 64):
            vecs = embedder.embed(texts[i : i + 64])
            for r, v in zip(rows[i : i + 64], vecs, strict=True):
                r.embedding = [float(x) for x in v]
                r.embedding_model = embedder.model_name
    db.add_all(rows)
    db.flush()
    return len(rows)


def search(db: Session, q: str, embedder: Embedder | None = None) -> list[Passage]:
    return retrieval.hybrid(db, q, embedder=embedder)


def searchable_count(db: Session) -> int:
    return (
        db.scalar(
            select(func.count(KnowledgeSource.id)).where(
                KnowledgeSource.review_status.in_(SEARCHABLE),
                KnowledgeSource.is_active.is_(True),
            )
        )
        or 0
    )
