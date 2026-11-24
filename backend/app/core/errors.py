"""Consistent error responses.

Every error leaves the API as:
    {"error": {"code": "string", "message": "string", "field": "optional"}}
Stack traces are never returned to clients (see API_CONTRACTS.md).
"""

import logging
from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import InterfaceError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("agrios.errors")


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AppError(Exception):
    """Domain error raised by services; mapped to the standard error envelope."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        field: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.field = field
        self.headers = headers


_HTTP_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    415: "unsupported_media_type",
    429: "rate_limited",
}


def error_body(code: str, message: str, field: str | None = None) -> dict[str, object]:
    return ErrorResponse(error=ErrorDetail(code=code, message=message, field=field)).model_dump(
        exclude_none=True
    )


def _field_from_loc(loc: tuple[object, ...]) -> str | None:
    # Drop the "body"/"query"/"path" prefix so the client sees the field name only.
    parts = [str(p) for p in loc[1:]] if len(loc) > 1 else [str(p) for p in loc]
    return ".".join(parts) or None


async def _app_error_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101 - narrowing for type checkers
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(exc.code, exc.message, exc.field),
        headers=exc.headers,
    )


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    first = exc.errors()[0] if exc.errors() else {}
    return JSONResponse(
        status_code=422,
        content=error_body(
            "validation_error",
            str(first.get("msg", "Invalid request")),
            _field_from_loc(tuple(first.get("loc", ()))),
        ),
    )


async def _http_handler(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    code = _HTTP_CODES.get(exc.status_code, "http_error")
    message = exc.detail if isinstance(exc.detail, str) else HTTPStatus(exc.status_code).phrase
    return JSONResponse(
        status_code=exc.status_code, content=error_body(code, message), headers=exc.headers
    )


async def _database_down_handler(request: Request, exc: Exception) -> JSONResponse:
    # Connection-level failures only (server down, refused, dropped). Query errors
    # such as constraint violations are NOT mapped here and stay 500 unless handled.
    logger.warning("database_unavailable", extra={"path": request.url.path})
    return JSONResponse(
        status_code=503,
        content=error_body(
            "database_unavailable", "The service is temporarily unavailable. Try again shortly."
        ),
    )


async def _unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500, content=error_body("internal_error", "An unexpected error occurred.")
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _app_error_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(StarletteHTTPException, _http_handler)
    app.add_exception_handler(OperationalError, _database_down_handler)
    app.add_exception_handler(InterfaceError, _database_down_handler)
    app.add_exception_handler(Exception, _unhandled_handler)
