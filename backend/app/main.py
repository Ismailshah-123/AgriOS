"""FastAPI application factory."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.v1.router import api_router
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging, request_logging_middleware
from app.db.session import Database
from app.storage.local import LocalFileStorage

API_PREFIX = "/api/v1"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    # Interactive docs are disabled in production unless API_DOCS_ENABLED=true.
    docs_enabled = settings.docs_enabled

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        stop = None
        if settings.embedded_worker and app.state.db.configured:
            from app.jobs.worker import start_embedded

            stop = start_embedded(app.state.db, app.state.storage, settings)
        yield
        if stop is not None:
            stop.set()
        app.state.db.dispose()

    app = FastAPI(
        lifespan=lifespan,
        title="AgriOS API",
        version=__version__,
        docs_url=f"{API_PREFIX}/docs" if docs_enabled else None,
        redoc_url=None,
        openapi_url=f"{API_PREFIX}/openapi.json" if docs_enabled else None,
    )
    app.state.settings = settings
    # Engine comes from the injected settings (not a global), so tests can point
    # the app at an isolated database.
    app.state.db = Database(settings)
    if settings.database_target_is_test and settings.app_env != "test":
        # Guard against silently running the real app on the throwaway test database.
        logging.getLogger("agrios.config").warning(
            "database_points_at_test_target", extra={"app_env": settings.app_env}
        )
    # Private storage for uploads (never mounted as static files).
    app.state.storage = LocalFileStorage(settings.storage_path)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        # Needed for the httpOnly refresh cookie. Safe because origins are explicit
        # (config rejects "*").
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )
    upload_limit = settings.upload_max_images * settings.upload_max_bytes + 1024 * 1024
    app.add_middleware(
        BodySizeLimitMiddleware,
        limit_for=lambda path: (
            upload_limit if path.startswith(f"{API_PREFIX}/cases") else 1024 * 1024
        ),
    )
    app.middleware("http")(request_logging_middleware)
    register_error_handlers(app)
    app.include_router(api_router, prefix=API_PREFIX)
    return app


app = create_app()
