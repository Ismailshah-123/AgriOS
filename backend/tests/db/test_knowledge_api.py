"""FR8 retrieval v1. ALL documents here are SYNTHETIC test fixtures about an invented crop
("zorblat"); they are not agricultural knowledge and exist only in the throwaway test DB."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.knowledge import service
from app.knowledge.models import CommercialUse, KnowledgeChunk, KnowledgeSource, SourceReview
from tests.support import API, register

pytestmark = pytest.mark.db

SYNTHETIC_TEXT = (
    "Zorblat test plants in this synthetic document are watered every third day.\n\n"
    "Leaf curl on the zorblat test plant is recorded as a synthetic example symptom."
)


def _source(db: Session, status: SourceReview, title: str) -> KnowledgeSource:
    s = KnowledgeSource(
        title=title,
        publisher="AgriOS test suite (SYNTHETIC)",
        licence="test-only",
        commercial_use=CommercialUse.UNKNOWN,
        language="en",
        review_status=status,
    )
    db.add(s)
    db.flush()
    return s


def test_unverified_sources_are_refused_and_never_searchable(
    db_client: TestClient, db_session: Session
) -> None:
    h = register(db_client, "kn@example.com")
    unverified = _source(db_session, SourceReview.UNVERIFIED, "Synthetic unverified doc")
    with pytest.raises(service.SourceNotVerified):
        service.ingest(db_session, unverified, [(1, None, SYNTHETIC_TEXT)])
    # Even a chunk written directly must not leak through search.
    db_session.add(KnowledgeChunk(source_id=unverified.id, position=0, text=SYNTHETIC_TEXT))
    db_session.flush()
    body = db_client.get(
        f"{API}/knowledge/search", params={"q": "zorblat watered"}, headers=h
    ).json()
    assert body["status"] == "no_verified_guidance" and body["passages"] == []
    assert "No verified guidance found" in body["message"] and body["searchable_sources"] == 0


def test_verified_source_returns_cited_extractive_passages(
    db_client: TestClient, db_session: Session
) -> None:
    h = register(db_client, "kn2@example.com")
    src = _source(db_session, SourceReview.LICENCE_VERIFIED, "Synthetic verified doc")
    assert service.ingest(db_session, src, [(7, "Watering", SYNTHETIC_TEXT)]) == 1
    body = db_client.get(
        f"{API}/knowledge/search", params={"q": "how often is zorblat watered"}, headers=h
    ).json()
    assert body["status"] == "found" and body["data_origin"] == "retrieved"
    top = body["passages"][0]
    assert "watered every third day" in top["text"]  # quoted verbatim, not generated
    assert (top["page"], top["section"], top["source"]["title"]) == (
        7,
        "Watering",
        "Synthetic verified doc",
    )
    miss = db_client.get(
        f"{API}/knowledge/search", params={"q": "wheat rust fungicide"}, headers=h
    ).json()
    assert miss["status"] == "no_verified_guidance"
    listed = db_client.get(f"{API}/knowledge/sources", headers=h).json()
    assert [s["review_status"] for s in listed] == ["licence_verified"]
    assert (
        db_client.get(f"{API}/knowledge/search", params={"q": "zo"}, headers=h).status_code == 422
    )


def test_chunking_keeps_paragraphs_and_overlap() -> None:
    long = " ".join(f"w{i}" for i in range(500))
    parts = service.chunk(long, max_words=220, overlap=40)
    assert all(len(p.split()) <= 220 for p in parts) and len(parts) == 3
    assert parts[1].split()[:40] == parts[0].split()[-40:]
    assert service.chunk("a b\n\nc d") == ["a b c d"]


def test_stats_count_the_real_library_and_name_untracked_telemetry(
    db_client: TestClient, db_session: Session
) -> None:
    h = register(db_client, "kn3@example.com")
    _source(db_session, SourceReview.UNVERIFIED, "Synthetic pending")
    src = _source(db_session, SourceReview.LICENCE_VERIFIED, "Synthetic ok")
    service.ingest(db_session, src, [(1, None, SYNTHETIC_TEXT)])
    s = db_client.get(f"{API}/knowledge/stats", headers=h).json()
    assert (
        s["sources_by_status"]["unverified"] == 1
        and s["sources_by_status"]["licence_verified"] == 1
    )
    assert (s["searchable_sources"], s["sources_with_chunks"], s["chunks"]) == (1, 1, 1)
    assert s["queries_total"] == 0 and "embedding cost" in s["not_tracked"]
