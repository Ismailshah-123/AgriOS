from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.db.session import Database
from app.main import create_app


def test_health_returns_ok(client: TestClient) -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body == {
        "status": "ok",
        "service": "agrios-api",
        "version": "0.1.0",
        "environment": "test",
    }


def test_health_sets_request_id_header(client: TestClient) -> None:
    res = client.get("/api/v1/health")
    assert len(res.headers["X-Request-ID"]) == 32


def test_request_id_is_echoed_when_safe(client: TestClient) -> None:
    res = client.get("/api/v1/health", headers={"X-Request-ID": "abc123"})
    assert res.headers["X-Request-ID"] == "abc123"


def test_unsafe_request_id_is_replaced(client: TestClient) -> None:
    res = client.get("/api/v1/health", headers={"X-Request-ID": "bad id\r\nx"})
    assert res.headers["X-Request-ID"] != "bad id\r\nx"


def test_ready_ok_when_database_reachable(
    client: TestClient, override_db_check: Callable[[str], None]
) -> None:
    override_db_check("ok")
    res = client.get("/api/v1/ready")
    assert res.status_code == 200
    assert res.json() == {"status": "ready", "checks": {"database": "ok"}}


@pytest.mark.parametrize("state", ["unavailable", "not_configured"])
def test_ready_503_when_database_not_usable(
    client: TestClient, override_db_check: Callable[[str], None], state: str
) -> None:
    override_db_check(state)
    res = client.get("/api/v1/ready")
    assert res.status_code == 503
    assert res.json() == {"status": "not_ready", "checks": {"database": state}}


def test_database_not_configured_reports_state(settings: Settings) -> None:
    assert Database(settings).check() == "not_configured"


def test_database_unavailable_never_raises(settings: Settings) -> None:
    # Port 1 on localhost: connection refused, no real database touched.
    s = settings.model_copy(
        update={
            "database_url": SecretStr("postgresql+psycopg://u:p@127.0.0.1:1/x"),
            "database_connect_timeout": 2,
        }
    )
    assert Database(s).check() == "unavailable"


def test_engine_uses_injected_settings_not_environment(
    settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env:env@envhost:5432/envdb")
    s = settings.model_copy(
        update={"database_url": SecretStr("postgresql+psycopg://u:p@injected:5432/injdb")}
    )
    app = create_app(s)
    assert app.state.db.engine.url.host == "injected"
    assert app.state.db.engine.url.database == "injdb"
