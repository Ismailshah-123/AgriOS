# RAG evaluation (2026-11-24)
Summary: repeatable evaluation on a development question set. Every number below is copied from a saved run file in `docs/09-rag-knowledge/eval/results/`. These are development-set results (thresholds were inspected on the same questions); they are **not** held-out test results and must not be presented as production accuracy.

## Set-up
- Question set: `eval/rag_dev_questions.json` — 27 answerable (23 EN, 2 Urdu, 2 Roman Urdu) + 6 unanswerable (library has no source). Gold = (source, section) pairs. **Labels were assigned by the AI coding assistant and are pending owner review.**
- Library: 18 licence-verified sources, 276 chunks (SOURCE_REGISTER.md).
- Runner: `cd backend; uv run python scripts/rag_eval.py ../docs/09-rag-knowledge/eval/rag_dev_questions.json --out ../docs/09-rag-knowledge/eval/results [--generate] [--rewrite]` (read-only; no rows written).
- Metrics at k = 5 on what the user receives (after thresholds + dedupe): hit@5 (any gold section), source-hit@5 (any gold document), recall@5, precision@5, MRR, nDCG@5, false-abstention rate, abstention accuracy on unanswerable.

## Results
| Run file | Arm | hit@5 | source-hit@5 | recall@5 | P@5 | MRR | nDCG@5 | false abst. | unanswerable abst. | retrieval p50 |
|---|---|---|---|---|---|---|---|---|---|---|
| rag_eval_20261124_160234 (v1: no title in embeddings) | full-text | 0.556 | — | 0.432 | 0.185 | 0.354 | 0.402 | 0 | 1/6 | 8.7 ms |
| same | hybrid | 0.630 | — | 0.463 | 0.254 | 0.494 | 0.561 | 0 | 5/6 | 49.7 ms |
| rag_eval_20261124_160449 (v2: title+section header in embeddings) | full-text | 0.593 | 0.852 | 0.457 | 0.185 | 0.364 | 0.406 | 0 | 1/6 | 7.0 ms |
| same | hybrid | 0.704 | 0.963 | 0.537 | 0.252 | 0.492 | 0.584 | 0 | 6/6 | 43.0 ms |
| rag_eval_20261124_160747_gen (v2 + LLM query rewrite) | hybrid | 0.741 | 0.963 | 0.574 | 0.274 | 0.523 | 0.646 | 0 | 6/6 | 36.3 ms |
(The full-text arm moved between v1 and v2 although its text is unchanged: re-indexing reorders equal-rank ties.)

By language (v2 + rewrite, hybrid): EN hit@5 0.696 (n=23), Urdu 1.0 (n=2), Roman Urdu 1.0 (n=2) — n is far too small for a language claim.

### Generation (run `rag_eval_20261124_160747_gen`, Groq `openai/gpt-oss-120b`, 27 answerable)
| Outcome | Count |
|---|---|
| answered (passed citation + groundedness checks) | 17 |
| rejected as ungrounded → quoted passages shown | 5 |
| LLM declined (`INSUFFICIENT_EVIDENCE`) | 4 |
| LLM error (HTTP 429, free-tier rate limit) | 1 |
Mean grounded share (English answers that were scored): 0.727. Invalid citations removed: 0 answers. Tokens: 40,823 prompt + 5,031 completion for 27 answers (+ rewrite calls); LLM latency p50 1.13 s. Cost on the Groq free tier: PKR 0 (rate-limited; the paid price is not quoted here).

## Interpretation (honest)
- Hybrid retrieval clearly beats keyword-only on this set (MRR 0.49 vs 0.36; unanswerable abstention 6/6 vs 1/6), and adding the document title to the embedded text raised hit@5 0.63 → 0.70.
- Section-level hit@5 (0.70–0.74) understates usefulness: source-level hit@5 is 0.96; many "misses" retrieved the article lead section instead of the labelled section.
- Weak spots seen: early blight vs late blight confusion (Phytophthora passages for an early-blight question), generic IPM passages outranking pest-specific ones.
- The groundedness check is lexical; it rejects some faithful paraphrases (5/27) — safe direction (falls back to quotes), not a faithfulness proof.
- Faithfulness, answer relevance and completeness were **not** human-rated. Embedding cost: none (local model).

## Regression protection
Unit + DB tests lock the behaviour that matters (tests/unit/test_knowledge_units.py, tests/db/test_knowledge_rag.py): licence gate, abstention, citation validation, dose removal, grounding fallback, Urdu dense retrieval, owner-scoped farm context, follow-ups. Re-run `rag_eval.py` after any change to chunking, embeddings, prompts or thresholds and compare with the table above.

## Next
Owner/expert review of gold labels; a separate held-out question set (written before looking at results); human rating of 30 answers for faithfulness/relevance; more Urdu questions; Pakistan-specific sources.
