"""RAG evaluation on the development question set. READ-ONLY: nothing is written to the DB.

uv run python scripts/rag_eval.py ../docs/09-rag-knowledge/eval/rag_dev_questions.json \
    --out ../docs/09-rag-knowledge/eval/results [--generate] [--rewrite]

Retrieval (what the user actually receives: thresholded, de-duplicated top passages), at the
section level (a passage is relevant if its (source title, section) is a gold pair):
  hit@5, recall@5 (gold sections found / gold sections), precision@5, MRR, nDCG@5,
  abstention accuracy on unanswerable questions, false-abstention rate on answerable ones,
  retrieval latency. Two arms: full-text only vs hybrid (full-text + dense, RRF).
--generate: also runs the LLM answer + validator on answerable questions (status, grounded
share, removed citations, token use). --rewrite: LLM query rewriting for non-English questions.
Writes one JSON run file per invocation; numbers may be reported only from these files.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.db import models_registry  # noqa: E402, F401
from app.db.session import Database  # noqa: E402
from app.knowledge import generation, query, retrieval  # noqa: E402
from app.knowledge.providers import LLMError, get_embedder, get_llm  # noqa: E402

K = 5


def _metrics(ranked: list[tuple[str, str]], gold: set[tuple[str, str]]) -> dict[str, float]:
    rel = [1 if r in gold else 0 for r in ranked[:K]]
    found = {r for r in ranked[:K] if r in gold}
    first = next((i for i, x in enumerate(rel, 1) if x), None)
    dcg = sum(x / math.log2(i + 1) for i, x in enumerate(rel, 1))
    idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(gold), K) + 1))
    return {
        "hit": float(bool(found)),
        "recall": len(found) / len(gold),
        "precision": (sum(rel) / len(rel)) if rel else 0.0,
        "mrr": 1 / first if first else 0.0,
        "ndcg": dcg / idcg if idcg else 0.0,
    }


def _retrieval_query(item: dict, llm: object | None) -> str:
    info = query.analyse(item["q"])
    if info.language == "en":
        return item["q"]
    if llm is not None:
        try:
            r = llm.chat(generation.rewrite_messages(item["q"], []), max_tokens=400, json_mode=True)  # type: ignore[attr-defined]
            rq, _ = generation.parse_rewrite(r.text)
            if rq:
                return f"{rq} {' '.join(query.glossary_terms(item['q']))}"
        except LLMError:
            pass
    return info.retrieval_terms


def run_arm(db, items, embedder, llm_rewrite) -> dict:  # noqa: ANN001
    rows, lat = [], []
    for it in items:
        rq = _retrieval_query(it, llm_rewrite)
        t0 = time.perf_counter()
        ps = retrieval.hybrid(db, rq, embedder=embedder, dense_query=rq)
        lat.append((time.perf_counter() - t0) * 1000)
        ranked = [(p.source["title"], p.section or "") for p in ps]
        row = {"id": it["id"], "lang": it["lang"], "retrieval_query": rq, "retrieved": ranked}
        if it.get("answerable", True):
            row.update(_metrics(ranked, {tuple(g) for g in it["gold"]}))
            gold_src = {g[0] for g in it["gold"]}
            row["source_hit"] = float(any(t in gold_src for t, _ in ranked[:K]))
            row["abstained"] = not ps
        else:
            row["correct_abstention"] = not ps
        rows.append(row)
    ans = [r for r in rows if "hit" in r]
    una = [r for r in rows if "correct_abstention" in r]

    def mean(key: str, subset: list[dict]) -> float | None:
        return round(statistics.mean(r[key] for r in subset), 4) if subset else None

    by_lang = {}
    for lang in sorted({r["lang"] for r in ans}):
        sub = [r for r in ans if r["lang"] == lang]
        by_lang[lang] = {"n": len(sub), "hit@5": mean("hit", sub), "mrr": mean("mrr", sub)}
    return {
        "summary": {
            "answerable_n": len(ans),
            "unanswerable_n": len(una),
            "hit@5": mean("hit", ans),
            "source_hit@5": mean("source_hit", ans),
            "recall@5": mean("recall", ans),
            "precision@5": mean("precision", ans),
            "mrr": mean("mrr", ans),
            "ndcg@5": mean("ndcg", ans),
            "false_abstention_rate": mean("abstained", ans),
            "abstention_accuracy_unanswerable": mean("correct_abstention", una),
            "retrieval_ms_p50": round(statistics.median(lat), 1),
            "retrieval_ms_max": round(max(lat), 1),
            "by_language": by_lang,
        },
        "rows": rows,
    }


def run_generation(db, items, embedder, llm) -> dict:  # noqa: ANN001
    rows = []
    for it in [i for i in items if i.get("answerable", True)]:
        rq = _retrieval_query(it, llm)
        ps = retrieval.hybrid(db, rq, embedder=embedder, dense_query=rq)
        if not ps:
            rows.append({"id": it["id"], "status": "abstained_no_evidence"})
            continue
        lang = "ur" if it["lang"].startswith("ur") else "en"
        try:
            r = llm.chat(generation.build_messages(it["q"], ps, it["lang"], None), max_tokens=1200)
        except LLMError as exc:
            rows.append({"id": it["id"], "status": f"llm_error:{exc}"})
            continue
        v = generation.validate(r.text, ps, has_farm=False, language=lang)
        if v.abstained:
            status = "abstained_by_llm"
        elif v.grounded_share is not None and v.grounded_share < 0.5:
            status = "rejected_ungrounded"
        else:
            status = "answered"
        rows.append(
            {
                "id": it["id"],
                "lang": it["lang"],
                "status": status,
                "grounded_share": v.grounded_share,
                "cited": v.cited,
                "warnings": v.warnings,
                "invalid_citations_removed": v.warnings.count("invalid_citation_removed"),
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "latency_ms": r.latency_ms,
                "model": r.model,
            }
        )
        time.sleep(2)  # free-tier rate limits
    gs = [r["grounded_share"] for r in rows if r.get("grounded_share") is not None]
    statuses: dict[str, int] = {}
    for r in rows:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    return {
        "summary": {
            "n": len(rows),
            "status_counts": statuses,
            "grounded_share_mean_en": round(statistics.mean(gs), 4) if gs else None,
            "answers_with_invalid_citation_removed": sum(
                1 for r in rows if r.get("invalid_citations_removed")
            ),
            "prompt_tokens": sum(r.get("prompt_tokens") or 0 for r in rows),
            "completion_tokens": sum(r.get("completion_tokens") or 0 for r in rows),
            "llm_latency_ms_p50": statistics.median(
                [r["latency_ms"] for r in rows if "latency_ms" in r]
            )
            if any("latency_ms" in r for r in rows)
            else None,
        },
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("questions", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--rewrite", action="store_true")
    a = ap.parse_args()
    settings = get_settings()
    qs = json.loads(a.questions.read_text(encoding="utf-8"))
    embedder = get_embedder(settings)
    llm = get_llm(settings)
    out = {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "question_set": a.questions.name,
        "labelled_by": qs.get("labelled_by"),
        "embedding_model": embedder.model_name if embedder else None,
        "thresholds": {
            "MIN_RANK": retrieval.MIN_RANK,
            "DENSE_MIN": retrieval.DENSE_MIN,
            "DENSE_SOFT": retrieval.DENSE_SOFT,
            "FTS_STRONG": retrieval.FTS_STRONG,
            "MAX_PASSAGES": retrieval.MAX_PASSAGES,
        },
        "llm_rewrite": bool(a.rewrite and llm),
    }
    with Database(settings).session() as db:
        out["fulltext_only"] = run_arm(db, qs["questions"], None, llm if a.rewrite else None)
        if embedder is not None:
            out["hybrid"] = run_arm(db, qs["questions"], embedder, llm if a.rewrite else None)
        if a.generate and llm is not None:
            out["generation"] = run_generation(db, qs["questions"], embedder, llm)
            out["generation_model"] = llm.model
        db.rollback()
    a.out.mkdir(parents=True, exist_ok=True)
    name = f"rag_eval_{datetime.now(UTC):%Y%m%d_%H%M%S}{'_gen' if a.generate else ''}.json"
    (a.out / name).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    for arm in ("fulltext_only", "hybrid"):
        if arm in out:
            print(arm, json.dumps(out[arm]["summary"], ensure_ascii=False))
    if "generation" in out:
        print("generation", json.dumps(out["generation"]["summary"]))
    print("saved", a.out / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
