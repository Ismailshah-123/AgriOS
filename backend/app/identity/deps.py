"""Authentication and authorization dependencies.

Minimum roles for the FYP: farmer (own data), expert (assigned cases, later),
admin (users/sources/models/audit, later). Ownership of records is checked in each
module's service, never only in routers.
"""

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_app_settings
from app.core.config import Settings
from app.core.errors import AppError
from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.identity.models import User, UserRole

_BEARER = {"WWW-Authenticate": "Bearer"}


def request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


RequestId = Annotated[str | None, Depends(request_id)]
DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_app_settings)]


def get_current_user(request: Request, db: DbSession, settings: AppSettings) -> User:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("not_authenticated", "Sign in to continue.", 401, headers=_BEARER)
    if settings.jwt_secret is None:
        raise AppError("auth_not_configured", "Authentication is not configured.", 503)
    try:
        claims = decode_access_token(token, settings.jwt_secret.get_secret_value())
    except TokenError as exc:
        message = "Your session has expired." if exc.code == "token_expired" else "Invalid token."
        raise AppError(exc.code, message, 401, headers=_BEARER) from exc
    user = db.get(User, claims.user_id)
    if user is None or not user.is_active:
        raise AppError("token_invalid", "Invalid token.", 401, headers=_BEARER)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed = frozenset(roles)

    def _check(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise AppError("forbidden", "You do not have permission for this action.", 403)
        return user

    return _check
