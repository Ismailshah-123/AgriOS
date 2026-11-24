"""Background worker: polls the DB job queue and runs handlers.

Run standalone:   cd backend && uv run python -m app.jobs.worker
Or embedded:      EMBEDDED_WORKER=true runs the same loop in a thread of the API process
                  (single-process development/demo only).
"""

import logging
import os
import signal
import socket
import threading
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.crop_health import analysis
from app.crop_health.service import ANALYSE_JOB
from app.db.session import Database
from app.jobs import queue
from app.jobs.models import Job
from app.knowledge import ingestion as knowledge_ingestion
from app.storage.base import Storage
from app.storage.local import LocalFileStorage

logger = logging.getLogger("agrios.worker")

Handler = Callable[[Session, Storage, Settings, Job], None]
HANDLERS: dict[str, Handler] = {
    ANALYSE_JOB: analysis.handle,
    knowledge_ingestion.INGEST_JOB: knowledge_ingestion.handle,
}


def run_once(db: Session, storage: Storage, settings: Settings, worker_id: str) -> bool:
    """Claim and process at most one job. Returns True if a job was processed."""
    job = queue.claim(db, worker_id, list(HANDLERS))
    if job is None:
        return False
    try:
        HANDLERS[job.kind](db, storage, settings, job)
    except Exception:  # handler bug: never crash the loop; record and retry later
        logger.exception("job_handler_crashed", extra={"job_id": str(job.id), "kind": job.kind})
        db.rollback()
        job = db.merge(job)
        queue.fail(db, job, "handler_crashed")
        db.commit()
    return True


def run_forever(
    database: Database,
    storage: Storage,
    settings: Settings,
    stop: threading.Event,
    poll_seconds: float = 2.0,
) -> None:
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{threading.get_ident()}"[:64]
    logger.info("worker_started", extra={"worker_id": worker_id})
    while not stop.is_set():
        try:
            with database.session() as db:
                processed = run_once(db, storage, settings, worker_id)
        except Exception:  # database down etc.: back off and keep going
            logger.exception("worker_iteration_failed")
            processed = False
        if not processed:
            stop.wait(poll_seconds)
    logger.info("worker_stopped", extra={"worker_id": worker_id})


def start_embedded(database: Database, storage: Storage, settings: Settings) -> threading.Event:
    stop = threading.Event()
    threading.Thread(
        target=run_forever,
        args=(database, storage, settings, stop),
        name="agrios-embedded-worker",
        daemon=True,
    ).start()
    return stop


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    run_forever(Database(settings), LocalFileStorage(settings.storage_path), settings, stop)


if __name__ == "__main__":
    main()
