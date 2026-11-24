# STORAGE_AND_WORKER.md — Crop Doctor storage and background processing
Status: Implemented for local/single-host (2026-11-23). Production object storage is a documented next step.

## Image storage
- Interface: `app/storage/base.py` (`put/get/delete/list`). Implementation: `LocalFileStorage(STORAGE_PATH)`; atomic writes, keys validated by pattern and confined to the root.
- Keys are generated only by the server: `crop-health/YYYY/MM/<uuid>-full.webp` and `-thumb.webp`. No user input reaches a path.
- Stored: re-encoded WebP derivatives (max 2048 px, thumbnail 480 px). EXIF/GPS/ICC removed. **Originals are not kept** (DATA_GOVERNANCE).
- Access: never a static/public mount. The API streams bytes after verifying an HMAC link (`signed_url_seconds`, default 600).
- Limits (env): `UPLOAD_MAX_BYTES` 8 MB, `UPLOAD_MAX_IMAGES` 5, `CASE_MAX_IMAGES` 20, `IMAGE_MAX_PIXELS` 40 MP, `IMAGE_MAX_SIDE` 8000, `IMAGE_MIN_SIDE` 128, `STORAGE_QUOTA_BYTES_PER_USER` 500 MB, `CASE_CREATE_LIMIT_PER_HOUR` 30.
- Consistency: validate in memory, then store, then commit; on failure, stored objects are deleted. `crop_health.service.sweep_orphans()` removes unreferenced objects older than 1 h (run periodically; scheduling it is pending).

## Production configuration (not yet implemented)
Use an S3-compatible bucket with an `S3Storage` implementing the same protocol: private bucket (block public access), server-side encryption, lifecycle rule for retention (DATA_GOVERNANCE default 12 months), credentials from env/secret store only, and the same API-side signed links (or short-lived presigned GETs). Back up the bucket with the database.

## Background processing
- Queue: `jobs` table; claim with `FOR UPDATE SKIP LOCKED`; partial unique index prevents duplicate pending jobs; retries with backoff (10 s, 60 s, 300 s); stale RUNNING jobs reclaimed after 10 min; all times use the database clock.
- Worker: `cd backend && uv run python -m app.jobs.worker` (separate process; recommended). `EMBEDDED_WORKER=true` runs it inside the API process for single-process dev/demo only.
- Compose: add a `worker` service with the same image and env as `api` (not yet added; Docker not installed on the dev machine).
