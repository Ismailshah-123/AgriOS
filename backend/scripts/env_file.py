"""Create/inspect backend/.env safely.

    uv run python scripts/env_file.py ensure   # create if missing; add a random JWT_SECRET
                                               # if absent; never overwrite existing values
    uv run python scripts/env_file.py check    # list missing/invalid settings (names only)

Never prints secret values. The file is git-ignored (.gitignore: .env, .env.*).
"""

import re
import secrets
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
REQUIRED = ("DATABASE_URL", "JWT_SECRET")
DEFAULTS = {
    "APP_ENV": "development",
    "LOG_LEVEL": "INFO",
    "ALLOWED_ORIGINS": "http://localhost:5173",
}
HEADER = (
    "# AgriOS backend settings for THIS machine. Git-ignored: never commit this file.\n"
    "# See .env.example (repo root) for every option.\n"
)


def read(path: Path = ENV_PATH) -> dict[str, str]:
    values: dict[str, str] = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*)\s*$", line)
            if m:
                values[m.group(1)] = m.group(2)
    return values


def set_missing(updates: dict[str, str], path: Path = ENV_PATH) -> list[str]:
    """Append keys that are not already present. Returns the names that were added."""
    current = read(path)
    added = [k for k in updates if k not in current]
    if not added:
        return []
    text = path.read_text(encoding="utf-8") if path.exists() else HEADER
    if not text.endswith("\n"):
        text += "\n"
    text += "".join(f"{k}={updates[k]}\n" for k in added)
    path.write_text(text, encoding="utf-8")
    return added


def problems(values: dict[str, str]) -> list[str]:
    issues = [f"{k} is not set" for k in REQUIRED if not values.get(k)]
    if values.get("JWT_SECRET") and len(values["JWT_SECRET"]) < 32:
        issues.append("JWT_SECRET is shorter than 32 characters")
    if values.get("DATABASE_URL") and not values["DATABASE_URL"].startswith(
        "postgresql+psycopg://"
    ):
        issues.append("DATABASE_URL must start with postgresql+psycopg://")
    return issues


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "ensure":
        added = set_missing({**DEFAULTS, "JWT_SECRET": secrets.token_urlsafe(48)})
        print(f"{ENV_PATH.name}: {'added ' + ', '.join(added) if added else 'no changes'}")
    issues = problems(read())
    for issue in issues:
        print(f"MISSING: {issue}")
    if not issues:
        print("backend/.env: required settings present")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
