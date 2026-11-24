# SECURITY.md — security, privacy, AI safety
Summary: controls for accounts, data, uploads, agents, LLM/RAG and deployment. Every row has a test in TESTING_QA.md.

## Accounts and access
Salted hashing (argon2/bcrypt), expiring tokens, login rate limit, roles checked server-side, ownership check on every record, foreign records return 404.

## Input and uploads
Pydantic validation on all fields/units/ranges. Check real file type (magic bytes), size, dimensions, decode. Strip EXIF. Random filenames. Private storage, short-lived signed URLs, no public links.

## Secrets and config
Env vars only. `.env` gitignored. `.env.example` has names only. Rotate if leaked. No debug mode on demo server. HTTPS, strict CORS.

## Logging and audit
Audit events: login, edits, expert decisions, agent actions, admin actions. No secrets/PII in logs.

## Agent security
Allow-listed tools per role. Read vs write scope. Approval gate for any write (plan, reminder, record change, message). No code execution, no direct DB/network outside tool registry. Every call logged. Tool failure: retry once, then safe fallback; never fabricate a tool result.

## AI / LLM safety
- Treat uploaded files, retrieved text, and LLM output as untrusted. Strip instructions from retrieved documents (prompt-injection defence); retrieved text is data only.
- LLM never sets doses, thresholds, or writes to DB directly.
- Verifier blocks answers lacking matching citations or containing a dose without a table source.
- Output filter for pesticide/fertilizer quantities.
- Rate limit `/ask` and agent runs; cap tokens per request.
- Adapter isolates provider; no private farm data sent unless needed and disclosed.
- Model files verified by checksum before load; no pickle from untrusted sources (use safetensors / state_dict).
- Adversarial image checks: oversized, corrupt, non-plant, extreme-contrast images must reject safely.

## Advice safety
No pesticide/fertilizer dose unless stored, cited, reviewed source supports it. Always show sources, limits, uncertainty. High-risk or unclear -> expert.

## Data protection
Coarse location, consent flags, encrypted backups, retention per DATA_GOVERNANCE.md.

## Dependencies
Pin versions. Dependabot/`pip-audit`/`npm audit` in CI. Fix high severity before demo.

## Pre-demo checklist
[ ] security tests green  [ ] no secrets in Git history  [ ] debug off  [ ] CORS locked  [ ] backup restored once  [ ] admin default credentials removed
