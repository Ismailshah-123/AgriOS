"""Shared fixtures.

Database tests are marked `@pytest.mark.db` and run ONLY against TEST_DATABASE_URL.
Safety rules (enforced, not advisory):
  * the database name must contain "test";
  * it must differ from DATABASE_URL;
  * if TEST_DATABASE_URL is unset, db tests are SKIPPED with a visible reason
    (never silently passed, never redirected to another database).
Each db test runs inside a transaction that is rolled back afterwards.
"""

import os
from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from alembic import command
from app.core.config import Settings
from app.db.session import get_db
from app.main import create_app
from tests.support import alembic_config, reset_schema


def test_database_url() -> str | None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return None
    name = make_url(url).database or ""
    if "test" not in name.lower():
        pytest.exit(f"Refusing to run: test database name '{name}' must contain 'test'.", 2)
    dev = os.environ.get("DATABASE_URL")
    if dev and make_url(dev) == make_url(url):
        pytest.exit("Refusing to run: TEST_DATABASE_URL equals DATABASE_URL.", 2)
    return url


test_database_url.__test__ = False  # type: ignore[attr-defined]  # not a test


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if test_database_url() is not None:
        return
    skip = pytest.mark.skip(reason="TEST_DATABASE_URL not set: database test skipped")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)


# ---------------------------------------------------------------- no-database fixtures


@pytest.fixture
def settings() -> Settings:
    # Explicit values so tests never depend on a developer's local .env.
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        app_env="test",
        database_url=None,
        allowed_origins=["http://localhost:5173"],
        jwt_secret=SecretStr("test-only-secret-key-that-is-long-enough-0123456789"),
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    return create_app(settings)


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture
def override_db_check(app: FastAPI) -> Callable[[str], None]:
    """Replace the real database probe with a fixed result (no DB needed)."""
    from app.api.v1.endpoints.health import get_database_checker

    def _set(state: str) -> None:
        app.dependency_overrides[get_database_checker] = lambda: lambda: state

    return _set


# ------------------------------------------------------------------- database fixtures


@pytest.fixture(scope="session")
def db_url() -> str:
    url = test_database_url()
    if url is None:  # pragma: no cover - collection already skips these tests
        pytest.skip("TEST_DATABASE_URL not set")
    return url


@pytest.fixture(scope="session")
def migrated_engine(db_url: str) -> Iterator[Engine]:
    engine = create_engine(db_url, pool_pre_ping=True)
    reset_schema(engine)
    command.upgrade(alembic_config(db_url), "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    connection = migrated_engine.connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        outer.rollback()
        connection.close()


@pytest.fixture
def db_settings(settings: Settings, db_url: str) -> Settings:
    return settings.model_copy(update={"database_url": SecretStr(db_url)})


@pytest.fixture
def db_app(db_settings: Settings, db_session: Session) -> FastAPI:
    application = create_app(db_settings)
    application.dependency_overrides[get_db] = lambda: db_session
    return application


@pytest.fixture
def db_client(db_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(db_app, raise_server_exceptions=False) as c:
        yield c
