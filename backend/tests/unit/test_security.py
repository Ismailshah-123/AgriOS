import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.audit.service import record
from app.core.rate_limit import SlidingWindowLimiter
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)

SECRET = "unit-test-secret-0123456789-abcdefghijklmnop"


def test_password_hash_is_salted_argon2_and_verifies() -> None:
    a, b = hash_password("correct horse battery"), hash_password("correct horse battery")
    assert a != b
    assert a.startswith("$argon2id$")
    assert verify_password("correct horse battery", a)
    assert not verify_password("wrong password!!", a)


def test_verify_against_missing_hash_is_false() -> None:
    assert verify_password("anything at all", None) is False


def test_access_token_round_trip() -> None:
    uid = uuid.uuid4()
    token, expires_in = create_access_token(uid, "farmer", SECRET, 15)
    claims = decode_access_token(token, SECRET)
    assert (claims.user_id, claims.role, expires_in) == (uid, "farmer", 900)


def test_expired_token_rejected_with_specific_code() -> None:
    past = datetime.now(UTC) - timedelta(hours=1)
    token, _ = create_access_token(uuid.uuid4(), "farmer", SECRET, 15, now=past)
    with pytest.raises(TokenError) as exc:
        decode_access_token(token, SECRET)
    assert exc.value.code == "token_expired"


@pytest.mark.parametrize(
    "token",
    [
        "not-a-jwt",
        jwt.encode({"sub": str(uuid.uuid4()), "role": "admin"}, key=None, algorithm="none"),
        jwt.encode(
            {
                "sub": str(uuid.uuid4()),
                "role": "farmer",
                "typ": "refresh",
                "iss": "agrios-api",
                "iat": datetime.now(UTC),
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            SECRET,
            algorithm="HS256",
        ),  # fmt: skip
    ],
    ids=["garbage", "alg-none", "wrong-typ"],
)
def test_invalid_tokens_rejected(token: str) -> None:
    with pytest.raises(TokenError) as exc:
        decode_access_token(token, SECRET)
    assert exc.value.code == "token_invalid"


def test_token_signed_with_other_secret_rejected() -> None:
    token, _ = create_access_token(uuid.uuid4(), "farmer", "x" * 40, 15)
    with pytest.raises(TokenError):
        decode_access_token(token, SECRET)


def test_refresh_tokens_are_random_and_stored_hashed() -> None:
    a, b = new_refresh_token(), new_refresh_token()
    assert a != b and len(a) >= 40
    assert hash_refresh_token(a) != a and len(hash_refresh_token(a)) == 64


def test_rate_limiter_window() -> None:
    lim = SlidingWindowLimiter(max_events=2, window_seconds=10)
    lim.hit("k", now=0)
    lim.hit("k", now=1)
    assert lim.retry_after("k", now=2) > 0
    assert lim.retry_after("k", now=10.5) == 0  # first event left the window
    lim.reset("k")
    assert lim.retry_after("k", now=2) == 0


def test_audit_refuses_secret_keys_in_meta() -> None:
    with pytest.raises(ValueError, match="password"):
        record(None, action="x", entity="y", meta={"password": "p"})  # type: ignore[arg-type]
