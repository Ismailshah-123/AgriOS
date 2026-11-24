"""Database unavailability must surface as a 503 envelope, never a 500."""

from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_db
from app.main import create_app


def _add_probe_route(app: FastAPI) -> None:
    @app.get("/api/v1/_probe")
    def probe(db: Annotated[Session, Depends(get_db)]) -> dict[str, int]:
        return {"one": db.execute(text("SELECT 1")).scalar_one()}


def test_db_dependency_503_when_not_configured(settings: Settings) -> None:
    app = create_app(settings)
    _add_probe_route(app)
    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.get("/api/v1/_probe")
    assert res.status_code == 503
    err = res.json()["error"]
    assert err["code"] == "database_unavailable"
    assert err["message"].startswith("The database is not configured.")
    assert "backend/.env" in err["message"]


def test_db_dependency_503_when_server_unreachable(settings: Settings) -> None:
    s = settings.model_copy(
        update={
            "database_url": SecretStr("postgresql+psycopg://u:secretpw@127.0.0.1:1/x"),
            "database_connect_timeout": 2,
        }
    )
    app = create_app(s)
    _add_probe_route(app)
    with TestClient(app, raise_server_exceptions=False) as client:
        res = client.get("/api/v1/_probe")
    assert res.status_code == 503
    assert res.json()["error"]["code"] == "database_unavailable"
    assert "secretpw" not in res.text
