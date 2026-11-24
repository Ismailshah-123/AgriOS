"""Engine and session management.

The engine is built from the Settings the running app was created with
(`app.state.db`), never from a global, so tests and alternative configs are
honoured. Creating an engine does not connect, so the app still starts without
a reachable database and reports that through /ready and 503 responses.
"""

import logging
from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import AppError

logger = logging.getLogger("agrios.db")

DATABASE_UNAVAILABLE = "database_unavailable"
# Actionable but secret-free: names the file and the guide, never values.
NOT_CONFIGURED_MESSAGE = (
    "The database is not configured. Set DATABASE_URL in backend/.env and run the "
    "database initialisation (see docs/13-user-guides/WINDOWS_LOCAL_SETUP.md)."
)


class Database:
    """Holds the engine and session factory for one application instance."""

    def __init__(self, settings: Settings) -> None:
        self.engine: Engine | None = None
        self._factory: sessionmaker[Session] | None = None
        if settings.database_url is not None:
            self.engine = create_engine(
                settings.database_url.get_secret_value(),
                pool_pre_ping=True,
                pool_size=5,
                connect_args={"connect_timeout": settings.database_connect_timeout},
            )
            self._factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    @property
    def configured(self) -> bool:
        return self.engine is not None

    def session(self) -> Session:
        if self._factory is None:
            raise AppError(DATABASE_UNAVAILABLE, NOT_CONFIGURED_MESSAGE, 503)
        return self._factory()

    def check(self) -> str:
        """Return 'ok', 'not_configured' or 'unavailable'. Never raises."""
        if self.engine is None:
            return "not_configured"
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return "ok"
        except Exception:  # noqa: BLE001 - any failure means "not ready"
            logger.warning("database_check_failed")
            return "unavailable"

    def dispose(self) -> None:
        if self.engine is not None:
            self.engine.dispose()


def get_database(request: Request) -> Database:
    db: Database = request.app.state.db
    return db


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed.

    Raises a 503 `database_unavailable` AppError when no database is configured;
    connection failures during the request are mapped to 503 by the error handlers.
    """
    session = get_database(request).session()
    try:
        yield session
    finally:
        session.close()
