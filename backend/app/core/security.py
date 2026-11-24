"""Password hashing and token primitives. Pure functions; no database access.

* Passwords: Argon2id via pwdlib (library defaults, salted, self-describing hash).
* Access tokens: short-lived HS256 JWT, `typ=access`, required claims enforced.
* Refresh tokens: 256-bit random opaque strings; only their SHA-256 is stored.
"""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()
# Verified against when the email is unknown, so login timing does not reveal
# whether an account exists.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))

JWT_ALGORITHM = "HS256"
JWT_ISSUER = "agrios-api"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if password_hash is None:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    role: str


class TokenError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code  # "token_expired" | "token_invalid"


def create_access_token(
    user_id: uuid.UUID, role: str, secret: str, minutes: int, now: datetime | None = None
) -> tuple[str, int]:
    issued = now or datetime.now(UTC)
    expires_in = minutes * 60
    payload = {
        "sub": str(user_id),
        "role": role,
        "typ": "access",
        "iss": JWT_ISSUER,
        "iat": issued,
        "exp": issued + timedelta(seconds=expires_in),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, secret, algorithm=JWT_ALGORITHM), expires_in


def decode_access_token(token: str, secret: str) -> AccessClaims:
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],  # never accept "none" or another algorithm
            issuer=JWT_ISSUER,
            options={"require": ["sub", "role", "typ", "iss", "iat", "exp"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("token_expired") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("token_invalid") from exc
    if payload.get("typ") != "access":
        raise TokenError("token_invalid")
    try:
        return AccessClaims(user_id=uuid.UUID(payload["sub"]), role=str(payload["role"]))
    except ValueError as exc:
        raise TokenError("token_invalid") from exc


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
