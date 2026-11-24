"""Typed, allow-listed agent tools (SECURITY: agents; CLAUDE.md hard rule 9).

Every tool declares: input schema, output schema, mode (read | write), required
permission, timeout, and a handler that calls an EXISTING owner-scoped service. There is
no tool for SQL, shell, file access or arbitrary code. `execute()` is the only entry point:
  - unknown tool                 -> ToolError("unknown_tool")
  - input fails its schema       -> ToolError("invalid_input")
  - write tool without approval  -> ToolError("approval_required")  (orchestrator turns
                                     this into a pending action; it never runs silently)
  - DB work beyond the timeout   -> ToolError("timeout")  (PostgreSQL statement_timeout;
                                     the weather provider has its own HTTP timeout)
  - handler output fails schema  -> ToolError("invalid_output")
Ownership is enforced inside the services (404 for another user's farm/field/cycle).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import AppError
from app.identity.models import User
from app.weather.provider import WeatherProvider


@dataclass
class ToolContext:
    db: Session
    user: User
    settings: Settings
    weather: WeatherProvider | None
    request_id: str | None = None


@dataclass
class ToolResult:
    status: Literal["ok", "unavailable"]
    data: dict[str, Any]
    summary: str
    evidence: list[dict[str, Any]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code, self.message = code, message


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    mode: Literal["read", "write"]
    permission: Literal["owner"]
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Callable[[ToolContext, Any], ToolResult]
    timeout_s: float = 10.0
    agents: tuple[str, ...] = ()

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode,
            "permission": self.permission,
            "requires_approval": self.mode == "write",
            "timeout_s": self.timeout_s,
            "agents": list(self.agents),
            "input_schema": self.input_model.model_json_schema(),
            "output_schema": self.output_model.model_json_schema(),
        }


TOOLS: dict[str, Tool] = {}


def register(tool: Tool) -> Tool:
    if tool.name in TOOLS:
        raise ValueError(f"duplicate tool {tool.name}")
    TOOLS[tool.name] = tool
    return tool


def validate_input(name: str, args: dict[str, Any]) -> tuple[Tool, BaseModel]:
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError("unknown_tool", f"Tool '{name}' is not allow-listed.")
    try:
        return tool, tool.input_model.model_validate(args)
    except ValidationError as e:
        raise ToolError("invalid_input", e.errors()[0]["msg"]) from e


def execute(
    ctx: ToolContext, name: str, args: dict[str, Any], *, approved: bool = False
) -> ToolResult:
    tool, parsed = validate_input(name, args)
    if tool.mode == "write" and not approved:
        raise ToolError("approval_required", f"'{name}' changes data and needs approval.")
    ctx.db.execute(text(f"SET LOCAL statement_timeout = {int(tool.timeout_s * 1000)}"))
    started = time.perf_counter()
    try:
        res = tool.handler(ctx, parsed)
    except AppError as e:
        ctx.db.rollback()
        code = "not_found" if e.status_code == 404 else e.code
        raise ToolError(code, e.message) from e
    except OperationalError as e:
        ctx.db.rollback()
        if "statement timeout" in str(e.orig):
            raise ToolError("timeout", f"'{name}' exceeded {tool.timeout_s}s.") from e
        raise ToolError("database_error", "A database error occurred.") from e
    if time.perf_counter() - started > tool.timeout_s * 3:  # outer guard (HTTP + DB)
        raise ToolError("timeout", f"'{name}' exceeded its time budget.")
    try:
        tool.output_model.model_validate(res.data)
    except ValidationError as e:
        raise ToolError("invalid_output", f"'{name}' returned malformed data.") from e
    return res
