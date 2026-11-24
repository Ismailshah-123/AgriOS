# CLAUDE_WORKFLOW.md — how Claude works on this repo
Summary: minimal-token working method, prompt template, review loop, what to refuse. CLAUDE.md links here.

## Token minimisation
1. Context is the budget. Start each module in a fresh session (`/clear`); `/compact` at ~60%.
2. Load only: CLAUDE.md (auto) + PROGRESS.md top + the one doc the task needs.
3. Search before reading: Grep/Glob, then Read with line ranges. Never `cat` big files, never read lockfiles, data, notebooks outputs, or model files.
4. Use Edit for small diffs. Avoid rewriting whole files. Split files over ~300 lines.
5. Pipe commands: `pytest -q -x 2>&1 | tail -30`. Show failures only.
6. Delegate broad exploration to the Explore subagent; keep only its conclusion.
7. Do not repeat the task, restate plans, or paste code back after writing it. Final reply: what changed + test result, 1-3 sentences.
8. Do not generate docs unless asked; update PROGRESS.md only.
9. Cheaper model for boilerplate/tests/CRUD; stronger model for architecture, ML design, security review.
10. Keep prompts specific: goal, inputs/outputs, rules, tests that must pass.

## Prompt template
```
Task: <one module/feature>
Read: <doc names only>
Inputs/outputs: <schemas>
Rules: <e.g. no invented doses, origin labels>
Tests that must pass: <list>
Done when: <acceptance from PRODUCT_REQUIREMENTS.md>
```

## Standard loop
plan (3 bullets max) -> write tests -> implement -> run tests -> fix -> update PROGRESS.md -> commit.

## Review loop (end of each phase)
Run full tests; check FEATURE_STATUS matches reality; grep for TODO and hard-coded secrets; confirm no result claims without run files.

## Must refuse / flag
- Invented datasets, accuracy, references, farmer feedback.
- Dose from LLM or unsourced.
- Attaching fake context to images.
- Code the developer cannot explain in the viva: add short comments on non-obvious logic, and keep a decision log in PROGRESS.md.
- Never paste secrets, private farm data, unpublished results into prompts.

## Decisions log
Append one line per decision to PROGRESS.md "Decisions" (date, decision, reason).

## Session start prompt (copy this)
`Read CLAUDE.md and the top of PROGRESS.md. Continue with Next tasks #1. Read only the docs needed.`

## Local environment rules (added Phase 3.7)
- Diagnose before changing: reproduce the error, then trace request -> settings -> database. Never guess.
- Never ask for, print or log database passwords; show URLs with the password hidden.
- The app database (backend/.env DATABASE_URL) and the test cluster (:54329, TEST_DATABASE_URL) must never be mixed; init_db.py refuses test targets.
- Only stop processes that scripts/dev/start.ps1 recorded; never kill unrelated processes (e.g. a developer's own server on :8000).
- Do not delete files or directories without explicit approval; list candidates in docs/15-progress/PROJECT_STRUCTURE.md.
