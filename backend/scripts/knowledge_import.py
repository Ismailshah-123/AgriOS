"""Operator CLI: register knowledge sources from a manifest and queue them for indexing.

uv run python scripts/knowledge_import.py ../docs/09-rag-knowledge/source_manifest.json \
    --files ../var/knowledge-sources [--dry-run]

Each manifest entry carries provenance + licence + the licence decision (`review_status` and
`review_note` with the evidence). Entries whose file is missing are skipped. Re-running is
idempotent: a source with the same file SHA-256 is left alone. Uses the same service code as
the admin API (licence gate, duplicate detection, audit events with actor = none, via = cli).
The background worker then indexes the queued sources. Never prints DATABASE_URL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.audit import service as audit  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.db import models_registry  # noqa: E402, F401 - complete metadata for FKs
from app.knowledge import ingestion  # noqa: E402
from app.knowledge.models import (  # noqa: E402
    CommercialUse,
    KnowledgeSource,
    SourceReview,
)
from app.storage.local import LocalFileStorage  # noqa: E402

FIELDS = (
    "title",
    "publisher",
    "author",
    "year",
    "url",
    "licence",
    "licence_url",
    "attribution",
    "language",
    "region",
    "country",
    "domain",
    "document_type",
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--files", type=Path, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--reindex-all",
        action="store_true",
        help="queue every verified, active source for re-indexing, then exit",
    )
    args = ap.parse_args()
    settings = get_settings()
    if settings.database_url is None:
        print("DATABASE_URL is not set")
        return 2
    engine = create_engine(settings.database_url.get_secret_value())
    if args.reindex_all:
        with Session(engine) as db:
            n = 0
            for s in db.scalars(select(KnowledgeSource)):
                if ingestion.enqueue_ingest(db, s):
                    audit.record(
                        db,
                        action="knowledge.source.reprocess",
                        entity="knowledge_source",
                        entity_id=s.id,
                        meta={"via": "cli"},
                    )
                    n += 1
            db.commit()
        print(f"queued {n} source(s) for re-indexing")
        return 0
    entries = json.loads(args.manifest.read_text(encoding="utf-8"))["sources"]
    storage = LocalFileStorage(settings.storage_path)
    added = skipped = 0
    with Session(engine) as db:
        for e in entries:
            path = args.files / e["file"]
            if not path.is_file():
                print(f"SKIP (file missing): {e['file']}")
                skipped += 1
                continue
            data = path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            if db.scalar(select(KnowledgeSource.id).where(KnowledgeSource.file_sha256 == sha)):
                print(f"exists: {e['title']}")
                skipped += 1
                continue
            if args.dry_run:
                print(f"would add: {e['title']} ({len(data)} bytes)")
                continue
            s = KnowledgeSource(
                **{k: e.get(k) for k in FIELDS},
                commercial_use=CommercialUse(e.get("commercial_use", "unknown")),
                crops=e.get("crops", []),
                publication_date=date.fromisoformat(e["publication_date"])
                if e.get("publication_date")
                else None,
                retrieved_at=datetime.fromisoformat(e["retrieved_at"])
                if e.get("retrieved_at")
                else datetime.now(UTC),
                review_status=SourceReview.UNVERIFIED,
                version=1,
                is_active=True,
                chunk_count=0,
                ingest_log=[],
            )
            db.add(s)
            db.flush()
            ingestion.log(s, "registered", via="cli")
            audit.record(
                db,
                action="knowledge.source.registered",
                entity="knowledge_source",
                entity_id=s.id,
                meta={"via": "cli", "title": s.title},
            )
            ingestion.attach_file(
                db, storage, settings, s, e["file"].split("/")[-1], data, actor_id=None
            )  # type: ignore[arg-type]
            status = SourceReview(e.get("review_status", "unverified"))
            if status != SourceReview.UNVERIFIED:
                ingestion.review(db, s, status, e["review_note"], actor_id=None)  # type: ignore[arg-type]
            db.commit()
            added += 1
            print(f"added: {s.title} -> {s.review_status.value}, {s.ingest_status.value}")
    print(f"done: {added} added, {skipped} skipped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
