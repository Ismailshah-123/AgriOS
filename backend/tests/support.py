"""Plain helpers shared by fixtures and tests (not fixtures themselves)."""

from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
API = "/api/v1"
PASSWORD = "a-long-test-password-1"


def alembic_config(url: str) -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.attributes["database_url"] = url
    return cfg


def reset_schema(engine: Engine) -> None:
    """Drop everything in the TEST database (callers are guarded by the name check)."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def register(client: TestClient, email: str, name: str = "Test Farmer") -> dict[str, str]:
    """Register a farmer and return Authorization headers."""
    res = client.post(
        f"{API}/auth/register", json={"email": email, "password": PASSWORD, "full_name": name}
    )
    assert res.status_code == 201, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def create_farm(client: TestClient, headers: dict[str, str], name: str = "Home Farm") -> dict:
    res = client.post(f"{API}/farms", headers=headers, json={"name": name})
    assert res.status_code == 201, res.text
    return res.json()


def create_field(
    client: TestClient,
    headers: dict[str, str],
    farm_id: str,
    name: str = "North Field",
    value: str = "2.5",
    unit: str = "acre",
) -> dict:
    res = client.post(
        f"{API}/fields",
        headers=headers,
        json={"farm_id": farm_id, "name": name, "area": {"value": value, "unit": unit}},
    )
    assert res.status_code == 201, res.text
    return res.json()


def crop_id(client: TestClient, headers: dict[str, str], code: str = "tomato") -> str:
    crops = client.get(f"{API}/crops", headers=headers).json()
    return next(c["id"] for c in crops if c["code"] == code)


def create_cycle(
    client: TestClient, headers: dict[str, str], field_id: str, **extra: object
) -> dict:
    body = {"field_id": field_id, "crop_id": crop_id(client, headers), **extra}
    res = client.post(f"{API}/crop-cycles", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()
