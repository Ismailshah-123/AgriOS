from fastapi import FastAPI, Query
from fastapi.testclient import TestClient

from app.core.errors import AppError


def test_unknown_route_uses_error_envelope(client: TestClient) -> None:
    res = client.get("/api/v1/does-not-exist")
    assert res.status_code == 404
    assert res.json() == {"error": {"code": "not_found", "message": "Not Found"}}


def test_wrong_method_uses_error_envelope(client: TestClient) -> None:
    res = client.post("/api/v1/health")
    assert res.status_code == 405
    assert res.json()["error"]["code"] == "method_not_allowed"


def test_validation_error_names_the_field(app: FastAPI) -> None:
    @app.get("/_probe/validation")
    def _probe(limit: int = Query(ge=1)) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as c:
        res = c.get("/_probe/validation", params={"limit": 0})
    assert res.status_code == 422
    err = res.json()["error"]
    assert err["code"] == "validation_error"
    assert err["field"] == "limit"


def test_app_error_maps_to_status_and_code(app: FastAPI) -> None:
    @app.get("/_probe/app-error")
    def _probe() -> None:
        raise AppError("file_too_large", "Image exceeds 8 MB.", status_code=413, field="file")

    with TestClient(app) as c:
        res = c.get("/_probe/app-error")
    assert res.status_code == 413
    assert res.json() == {
        "error": {"code": "file_too_large", "message": "Image exceeds 8 MB.", "field": "file"}
    }


def test_unhandled_exception_hides_internals(app: FastAPI) -> None:
    @app.get("/_probe/crash")
    def _probe() -> None:
        raise RuntimeError("secret internal detail")

    with TestClient(app, raise_server_exceptions=False) as c:
        res = c.get("/_probe/crash")
    assert res.status_code == 500
    assert res.json() == {
        "error": {"code": "internal_error", "message": "An unexpected error occurred."}
    }
    assert "secret" not in res.text


def test_cors_allows_configured_origin(client: TestClient) -> None:
    res = client.get("/api/v1/health", headers={"Origin": "http://localhost:5173"})
    assert res.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin(client: TestClient) -> None:
    res = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in res.headers
