import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.core.config import Settings
from app.core.security import create_access_token
from app.identity.deps import require_roles
from app.identity.models import User, UserRole
from app.identity.router import REFRESH_COOKIE
from tests.support import API, PASSWORD, register

pytestmark = pytest.mark.db


def _login(client: TestClient, email: str, password: str = PASSWORD):  # noqa: ANN202
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


# ---------------------------------------------------------------- registration


def test_register_creates_farmer_sets_cookie_and_audits(
    db_client: TestClient, db_session: Session
) -> None:
    res = db_client.post(
        f"{API}/auth/register",
        json={"email": " Ali@Example.COM ", "password": PASSWORD, "full_name": "  Ali Khan "},
    )
    assert res.status_code == 201
    body = res.json()
    assert body["user"]["email"] == "ali@example.com"
    assert body["user"]["full_name"] == "Ali Khan"
    assert body["user"]["role"] == "farmer"
    assert body["token_type"] == "bearer" and body["expires_in"] == 900
    cookie = res.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api/v1/auth" in cookie
    user = db_session.scalar(select(User).where(User.email == "ali@example.com"))
    assert user is not None and user.password_hash.startswith("$argon2id$")
    actions = db_session.scalars(select(AuditEvent.action).where(AuditEvent.actor_id == user.id))
    assert list(actions) == ["user.registered"]


def test_register_duplicate_email_is_case_insensitive(db_client: TestClient) -> None:
    register(db_client, "dup@example.com")
    res = db_client.post(
        f"{API}/auth/register",
        json={"email": "DUP@example.com", "password": PASSWORD, "full_name": "X"},
    )
    assert res.status_code == 409
    assert res.json()["error"] == {
        "code": "email_taken",
        "message": "An account with this email already exists.",
        "field": "email",
    }


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"email": "a@example.com", "password": "short", "full_name": "A"}, "password"),
        ({"email": "not-an-email", "password": PASSWORD, "full_name": "A"}, "email"),
        ({"email": "a@example.com", "password": PASSWORD, "full_name": "   "}, "full_name"),
        (
            {"email": "a@example.com", "password": PASSWORD, "full_name": "A", "role": "admin"},
            "role",
        ),  # fmt: skip
    ],
    ids=["short-password", "bad-email", "blank-name", "self-assigned-role"],
)
def test_register_validation(db_client: TestClient, payload: dict, field: str) -> None:
    res = db_client.post(f"{API}/auth/register", json=payload)
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "validation_error"
    assert res.json()["error"]["field"] == field


# ---------------------------------------------------------------------- login


def test_login_success_and_me(db_client: TestClient) -> None:
    register(db_client, "me@example.com", "Me Farmer")
    res = _login(db_client, "ME@example.com")
    assert res.status_code == 200
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}
    me = db_client.get(f"{API}/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["full_name"] == "Me Farmer"
    assert "password_hash" not in me.json()


def test_login_failure_does_not_reveal_whether_account_exists(db_client: TestClient) -> None:
    register(db_client, "real@example.com")
    wrong_pw = _login(db_client, "real@example.com", "wrong-password-123")
    no_user = _login(db_client, "ghost@example.com", "wrong-password-123")
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_login_rate_limited_after_five_failures(db_client: TestClient) -> None:
    register(db_client, "rl@example.com")
    for _ in range(5):
        assert _login(db_client, "rl@example.com", "wrong-password-123").status_code == 401
    res = _login(db_client, "rl@example.com")  # even the right password is blocked now
    assert res.status_code == 429
    assert res.json()["error"]["code"] == "rate_limited"
    assert int(res.headers["Retry-After"]) > 0


# ---------------------------------------------------------------------- tokens


def test_me_requires_bearer_token(db_client: TestClient) -> None:
    res = db_client.get(f"{API}/auth/me")
    assert res.status_code == 401
    assert res.headers["WWW-Authenticate"] == "Bearer"
    assert res.json()["error"]["code"] == "not_authenticated"


def test_expired_and_tampered_tokens_rejected(db_client: TestClient, db_settings: Settings) -> None:
    headers = register(db_client, "tok@example.com")
    me = db_client.get(f"{API}/auth/me", headers=headers).json()
    secret = db_settings.jwt_secret.get_secret_value()  # type: ignore[union-attr]
    old, _ = create_access_token(
        uuid.UUID(me["id"]), "farmer", secret, 15, now=datetime.now(UTC) - timedelta(hours=1)
    )
    res = db_client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {old}"})
    assert res.status_code == 401 and res.json()["error"]["code"] == "token_expired"
    tampered = headers["Authorization"][:-3] + "abc"
    res = db_client.get(f"{API}/auth/me", headers={"Authorization": tampered})
    assert res.status_code == 401 and res.json()["error"]["code"] == "token_invalid"


def test_token_of_deactivated_user_rejected(db_client: TestClient, db_session: Session) -> None:
    headers = register(db_client, "off@example.com")
    user = db_session.scalar(select(User).where(User.email == "off@example.com"))
    assert user is not None
    user.is_active = False
    db_session.flush()
    assert db_client.get(f"{API}/auth/me", headers=headers).status_code == 401
    assert _login(db_client, "off@example.com").status_code == 401


# --------------------------------------------------------------------- refresh


def test_refresh_rotates_and_detects_reuse(db_client: TestClient) -> None:
    register(db_client, "rot@example.com")
    first = db_client.cookies.get(REFRESH_COOKIE)
    res = db_client.post(f"{API}/auth/refresh")
    assert res.status_code == 200 and res.json()["access_token"]
    second = db_client.cookies.get(REFRESH_COOKIE)
    assert second and second != first
    # Replaying the rotated token ends the whole session family...
    db_client.cookies.clear()
    db_client.cookies.set(REFRESH_COOKIE, first)  # type: ignore[arg-type]
    assert db_client.post(f"{API}/auth/refresh").status_code == 401
    # ...including the newest token.
    db_client.cookies.clear()
    db_client.cookies.set(REFRESH_COOKIE, second)
    res = db_client.post(f"{API}/auth/refresh")
    assert res.status_code == 401 and res.json()["error"]["code"] == "session_expired"


def test_refresh_without_cookie_or_from_foreign_origin(db_client: TestClient) -> None:
    assert db_client.post(f"{API}/auth/refresh").status_code == 401
    register(db_client, "orig@example.com")
    res = db_client.post(f"{API}/auth/refresh", headers={"Origin": "https://evil.example"})
    assert res.status_code == 403 and res.json()["error"]["code"] == "origin_not_allowed"


def test_logout_revokes_refresh_token(db_client: TestClient) -> None:
    register(db_client, "out@example.com")
    token = db_client.cookies.get(REFRESH_COOKIE)
    assert db_client.post(f"{API}/auth/logout").status_code == 204
    db_client.cookies.set(REFRESH_COOKIE, token)  # type: ignore[arg-type]
    assert db_client.post(f"{API}/auth/refresh").status_code == 401


# --------------------------------------------------------------------- profile


def test_profile_update_audits_field_names_only(db_client: TestClient, db_session: Session) -> None:
    headers = register(db_client, "prof@example.com")
    res = db_client.patch(
        f"{API}/users/me", headers=headers, json={"full_name": "New Name", "locale": "ur"}
    )
    assert res.status_code == 200
    assert (res.json()["full_name"], res.json()["locale"]) == ("New Name", "ur")
    event = db_session.scalar(select(AuditEvent).where(AuditEvent.action == "user.profile_updated"))
    assert event is not None and event.meta == {"fields": ["full_name", "locale"]}
    escalate = db_client.patch(f"{API}/users/me", headers=headers, json={"role": "admin"})
    assert escalate.status_code == 422


def test_change_password_signs_out_other_sessions(db_client: TestClient) -> None:
    headers = register(db_client, "pw@example.com")
    old_refresh = db_client.cookies.get(REFRESH_COOKIE)
    bad = db_client.post(
        f"{API}/users/me/password", headers=headers,
        json={"current_password": "not-the-password", "new_password": "another-long-password"},
    )  # fmt: skip
    assert bad.status_code == 400 and bad.json()["error"]["field"] == "current_password"
    ok = db_client.post(
        f"{API}/users/me/password", headers=headers,
        json={"current_password": PASSWORD, "new_password": "another-long-password"},
    )  # fmt: skip
    assert ok.status_code == 204
    db_client.cookies.set(REFRESH_COOKIE, old_refresh)  # type: ignore[arg-type]
    assert db_client.post(f"{API}/auth/refresh").status_code == 401
    assert _login(db_client, "pw@example.com").status_code == 401
    assert _login(db_client, "pw@example.com", "another-long-password").status_code == 200


# ----------------------------------------------------------------------- roles


def test_require_roles_blocks_farmer(db_app: FastAPI) -> None:
    @db_app.get(f"{API}/_admin_probe")
    def probe(_: User = Depends(require_roles(UserRole.ADMIN))) -> dict[str, bool]:  # noqa: B008
        return {"ok": True}

    with TestClient(db_app) as client:
        headers = register(client, "role@example.com")
        res = client.get(f"{API}/_admin_probe", headers=headers)
    assert res.status_code == 403 and res.json()["error"]["code"] == "forbidden"


def test_audit_log_never_contains_secrets(db_client: TestClient, db_session: Session) -> None:
    register(db_client, "sec@example.com")
    _login(db_client, "sec@example.com", "wrong-password-123")
    db_client.post(f"{API}/auth/refresh")
    for event in db_session.scalars(select(AuditEvent)):
        dumped = str(event.meta).lower()
        assert PASSWORD not in dumped and "token" not in dumped and "argon2" not in dumped
