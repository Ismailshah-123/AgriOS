"""Short-lived signed links for private images (API_CONTRACTS: "no public URLs (signed,
short-lived)"). <img> tags cannot send a Bearer token, so the owner-scoped case endpoint
issues links; the signature binds image id, variant, expiry AND the owner id, which the
file endpoint re-checks against the database."""

import hashlib
import hmac
import time
import uuid


def _key(secret: str) -> bytes:
    # Separate key derived from the app secret so file links cannot be used as JWTs.
    return hashlib.sha256(f"agrios-file-links:{secret}".encode()).digest()


def _message(image_id: uuid.UUID, variant: str, owner_id: uuid.UUID, exp: int) -> bytes:
    return f"{image_id}|{variant}|{owner_id}|{exp}".encode()


def sign(
    image_id: uuid.UUID,
    variant: str,
    owner_id: uuid.UUID,
    ttl: int,
    secret: str,
    now: float | None = None,
) -> tuple[int, str]:
    exp = int((now or time.time()) + ttl)
    sig = hmac.new(_key(secret), _message(image_id, variant, owner_id, exp), hashlib.sha256)
    return exp, sig.hexdigest()


def verify(
    image_id: uuid.UUID,
    variant: str,
    owner_id: uuid.UUID,
    exp: int,
    sig: str,
    secret: str,
    now: float | None = None,
) -> bool:
    if exp < (now or time.time()):
        return False
    expected = hmac.new(_key(secret), _message(image_id, variant, owner_id, exp), hashlib.sha256)
    return hmac.compare_digest(expected.hexdigest(), sig)
