"""Identity service: registration, authentication, refresh rotation, profile.

Public registration always creates a FARMER. Expert and admin accounts are created
by an administrator (seed/CLI) and never through the public endpoint.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit import service as audit
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.identity.models import RefreshToken, User, UserRole
from app.identity.schemas import PasswordChange, ProfileUpdate, RegisterRequest

_INVALID_CREDENTIALS = AppError("invalid_credentials", "Email or password is incorrect.", 401)
_INVALID_REFRESH = AppError("session_expired", "Your session has ended. Please sign in.", 401)


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    expires_in: int
    refresh_token: str


def _secret(settings: Settings) -> str:
    if settings.jwt_secret is None:
        raise AppError("auth_not_configured", "Authentication is not configured.", 503)
    return settings.jwt_secret.get_secret_value()


def get_by_email(db: Session, email: str) -> User | None:
    return db.scalar(select(User).where(User.email == email))


def register(db: Session, data: RegisterRequest, request_id: str | None) -> User:
    if get_by_email(db, data.email) is not None:
        raise AppError("email_taken", "An account with this email already exists.", 409, "email")
    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        full_name=data.full_name,
        role=UserRole.FARMER,
        locale=data.locale,
    )
    db.add(user)
    db.flush()
    audit.record(
        db, action="user.registered", entity="user", entity_id=user.id,
        actor_id=user.id, request_id=request_id,
    )  # fmt: skip
    db.commit()
    return user


def authenticate(db: Session, email: str, password: str, request_id: str | None) -> User:
    user = get_by_email(db, email)
    ok = verify_password(password, user.password_hash if user else None)
    if user is None or not ok or not user.is_active:
        if user is not None:
            audit.record(
                db, action="auth.login_failed", entity="user", entity_id=user.id,
                actor_id=user.id, request_id=request_id,
            )  # fmt: skip
            db.commit()
        raise _INVALID_CREDENTIALS
    user.last_login_at = datetime.now(UTC)
    audit.record(
        db, action="auth.login", entity="user", entity_id=user.id,
        actor_id=user.id, request_id=request_id,
    )  # fmt: skip
    return user


def issue_tokens(
    db: Session, user: User, settings: Settings, family_id: uuid.UUID | None = None
) -> IssuedTokens:
    access, expires_in = create_access_token(
        user.id, user.role.value, _secret(settings), settings.access_token_minutes
    )
    raw = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id or uuid.uuid4(),
            token_hash=hash_refresh_token(raw),
            expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    return IssuedTokens(access, expires_in, raw)


def _revoke_family(db: Session, family_id: uuid.UUID) -> None:
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )


def rotate(
    db: Session, raw: str | None, settings: Settings, request_id: str | None
) -> tuple[User, IssuedTokens]:
    if not raw:
        raise _INVALID_REFRESH
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
    )
    if token is None:
        raise _INVALID_REFRESH
    if token.revoked_at is not None:
        # A rotated token was replayed: assume theft, end every session in the family.
        _revoke_family(db, token.family_id)
        audit.record(
            db, action="auth.refresh_reuse_detected", entity="user", entity_id=token.user_id,
            actor_id=token.user_id, request_id=request_id,
        )  # fmt: skip
        db.commit()
        raise _INVALID_REFRESH
    user = db.get(User, token.user_id)
    if token.expires_at <= datetime.now(UTC) or user is None or not user.is_active:
        raise _INVALID_REFRESH
    token.revoked_at = datetime.now(UTC)
    return user, issue_tokens(db, user, settings, family_id=token.family_id)


def logout(db: Session, raw: str | None, request_id: str | None) -> None:
    if not raw:
        return
    token = db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw))
    )
    if token is None:
        return
    _revoke_family(db, token.family_id)
    audit.record(
        db, action="auth.logout", entity="user", entity_id=token.user_id,
        actor_id=token.user_id, request_id=request_id,
    )  # fmt: skip
    db.commit()


def update_profile(db: Session, user: User, data: ProfileUpdate, request_id: str | None) -> User:
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(user, field, value)
    if changes:
        audit.record(
            db, action="user.profile_updated", entity="user", entity_id=user.id,
            actor_id=user.id, meta={"fields": sorted(changes)}, request_id=request_id,
        )  # fmt: skip
    db.commit()
    return user


def change_password(db: Session, user: User, data: PasswordChange, request_id: str | None) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise AppError(
            "invalid_credentials", "Current password is incorrect.", 400, "current_password"
        )
    user.password_hash = hash_password(data.new_password)
    # Sign out every other session.
    db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    audit.record(
        db, action="user.password_changed", entity="user", entity_id=user.id,
        actor_id=user.id, request_id=request_id,
    )  # fmt: skip
    db.commit()
