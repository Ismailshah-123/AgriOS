"""Cursor pagination (API_CONTRACTS: `?limit=&cursor=`).

Lists are ordered newest first by (created_at, id). The cursor is an opaque,
URL-safe token encoding the last row's sort key; clients must not parse it.
"""

import base64
import json
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import Query
from pydantic import BaseModel
from sqlalchemy import Select, and_, or_

from app.core.errors import AppError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100

Limit = Annotated[int, Query(ge=1, le=MAX_LIMIT)]
Cursor = Annotated[str | None, Query(max_length=200)]


class Page[T](BaseModel):
    items: list[T]
    next_cursor: str | None


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        created, row_id = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(created), uuid.UUID(row_id)
    except (ValueError, TypeError) as exc:
        raise AppError("invalid_cursor", "The page cursor is invalid.", 422, "cursor") from exc


def paginate(stmt: Select[Any], model: Any, limit: int, cursor: str | None) -> Select[Any]:
    """Apply keyset ordering + filtering; fetches limit+1 rows to detect a next page."""
    if cursor:
        created, row_id = decode_cursor(cursor)
        stmt = stmt.where(
            or_(model.created_at < created, and_(model.created_at == created, model.id < row_id))
        )
    return stmt.order_by(model.created_at.desc(), model.id.desc()).limit(limit + 1)


def to_page[T: BaseModel](items: list[T], limit: int) -> Page[T]:
    """`items` are output models (with created_at and id) built from limit+1 rows."""
    has_more = len(items) > limit
    items = items[:limit]
    last = items[-1] if items else None
    next_cursor = (
        encode_cursor(last.created_at, last.id)  # type: ignore[attr-defined]
        if has_more and last is not None
        else None
    )
    return Page[T](items=items, next_cursor=next_cursor)
