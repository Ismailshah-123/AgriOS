"""Auth endpoints. Access token in the JSON body (kept in memory by the client);
refresh token only in an httpOnly, SameSite=Strict cookie scoped to /api/v1/auth."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Request, Response, status

from app.core.config import Settings
from app.core.errors import AppError
from app.core.rate_limit import SlidingWindowLimiter
from app.identity import service
from app.identity.deps import AppSettings, CurrentUser, DbSession, RequestId
from app.identity.schemas import (
    LoginRequest,
    PasswordChange,
    ProfileUpdate,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

REFRESH_COOKIE = "agrios_refresh"
REFRESH_COOKIE_PATH = "/api/v1/auth"

router = APIRouter(tags=["auth"])
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _limiters(request: Request) -> tuple[SlidingWindowLimiter, SlidingWindowLimiter]:
    state = request.app.state
    if not hasattr(state, "login_limiter"):
        state.login_limiter = SlidingWindowLimiter(max_events=5, window_seconds=300)
        settings: Settings = state.settings
        state.register_limiter = SlidingWindowLimiter(
            max_events=settings.register_limit_per_hour, window_seconds=3600
        )
    return state.login_limiter, state.register_limiter


def _enforce(limiter: SlidingWindowLimiter, key: str) -> None:
    wait = limiter.retry_after(key)
    if wait:
        raise AppError(
            "rate_limited",
            f"Too many attempts. Try again in {wait} seconds.",
            429,
            headers={"Retry-After": str(wait)},
        )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _check_origin(request: Request, settings: Settings) -> None:
    # Cookie-authenticated endpoints: reject cross-site browser requests (CSRF defence
    # in depth on top of SameSite=Strict). Non-browser clients send no Origin.
    origin = request.headers.get("origin")
    if origin is not None and origin.rstrip("/") not in settings.allowed_origins:
        raise AppError("origin_not_allowed", "Request origin is not allowed.", 403)


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        max_age=settings.refresh_token_days * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )


def _token_response(user: object, tokens: service.IssuedTokens) -> TokenResponse:
    return TokenResponse(
        access_token=tokens.access_token,
        expires_in=tokens.expires_in,
        user=UserOut.model_validate(user),
    )


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    data: RegisterRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    rid: RequestId,
) -> TokenResponse:
    _, register_limiter = _limiters(request)
    ip_key = _client_ip(request)
    _enforce(register_limiter, ip_key)
    register_limiter.hit(ip_key)
    user = service.register(db, data, rid)
    tokens = service.issue_tokens(db, user, settings)
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return _token_response(user, tokens)


@router.post("/auth/login", response_model=TokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    rid: RequestId,
) -> TokenResponse:
    login_limiter, _ = _limiters(request)
    key = f"{_client_ip(request)}|{data.email}"
    _enforce(login_limiter, key)
    try:
        user = service.authenticate(db, data.email, data.password, rid)
    except AppError:
        login_limiter.hit(key)  # only failures count towards the limit
        raise
    login_limiter.reset(key)
    tokens = service.issue_tokens(db, user, settings)
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return _token_response(user, tokens)


@router.post("/auth/refresh", response_model=TokenResponse)
def refresh(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    rid: RequestId,
    refresh_token: RefreshCookie = None,
) -> TokenResponse:
    _check_origin(request, settings)
    user, tokens = service.rotate(db, refresh_token, settings, rid)
    _set_refresh_cookie(response, tokens.refresh_token, settings)
    return _token_response(user, tokens)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
    rid: RequestId,
    refresh_token: RefreshCookie = None,
) -> None:
    _check_origin(request, settings)
    service.logout(db, refresh_token, rid)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("/users/me", response_model=UserOut)
def update_me(data: ProfileUpdate, user: CurrentUser, db: DbSession, rid: RequestId) -> UserOut:
    return UserOut.model_validate(service.update_profile(db, user, data, rid))


@router.post("/users/me/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(data: PasswordChange, user: CurrentUser, db: DbSession, rid: RequestId) -> None:
    service.change_password(db, user, data, rid)
