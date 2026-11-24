"""Initialise or verify the application database. Safe to run any number of times.

    uv run python scripts/init_db.py          # check, then apply pending migrations
    uv run python scripts/init_db.py --check  # check only; never changes anything

Steps: load backend/.env -> refuse test targets -> connect -> report current revision ->
`alembic upgrade head` (additive; never drops or resets data) -> verify required tables ->
report the final revision. Exit codes: 0 ok, 2 not configured, 3 refused target,
4 cannot connect, 5 database missing, 6 migration failed, 7 tables missing, 8 behind head.
Passwords are never printed (URLs are shown with the password hidden).
"""

import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from alembic.config import Config  # noqa: E402
from alembic.runtime.migration import MigrationContext  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402

from alembic import command  # noqa: E402
from app.core.config import get_settings  # noqa: E402

REQUIRED_TABLES = {
    "users",
    "refresh_tokens",
    "audit_events",
    "farms",
    "fields",
    "crop_definitions",
    "crop_cycles",
    "diagnosis_cases",
    "case_submissions",
    "case_images",
    "diagnosis_predictions",
    "model_versions",
    "jobs",
    "weather_snapshots",
    "soil_observations",
    "agent_runs",
    "agent_steps",
    "agent_actions",
    "expenses",
    "harvest_sales",
    "expert_reviews",
    "knowledge_sources",
    "knowledge_chunks",
    "knowledge_conversations",
    "knowledge_queries",
}


def fail(code: int, message: str) -> int:
    print(f"ERROR: {message}")
    return code


def main() -> int:
    check_only = "--check" in sys.argv
    settings = get_settings()
    if settings.database_url is None:
        return fail(
            2,
            "DATABASE_URL is not set in backend/.env (see WINDOWS_LOCAL_SETUP.md).",
        )
    raw = settings.database_url.get_secret_value()
    url = make_url(raw)
    shown = url.render_as_string(hide_password=True)
    if settings.database_target_is_test and "--allow-test" not in sys.argv:
        return fail(
            3, f"Refusing to initialise a test database ({shown}). Use your development database."
        )
    print(f"Database: {shown}")

    engine = create_engine(raw, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
    except OperationalError as exc:
        text = str(exc.orig or exc).lower()
        if "does not exist" in text and "database" in text:
            return fail(
                5,
                f"Database '{url.database}' does not exist on {url.host}:{url.port}. "
                "Create it first (setup guide, step 4).",
            )
        if "password authentication failed" in text or "authentication" in text:
            return fail(
                4,
                f"Authentication failed for user '{url.username}'. "
                "Check DATABASE_URL in backend/.env.",
            )
        return fail(4, f"Cannot connect to PostgreSQL at {url.host}:{url.port}. Is it running?")
    finally:
        engine.dispose()

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.attributes["database_url"] = raw
    head = ScriptDirectory.from_config(cfg).get_current_head()
    print(f"Revision before: {current or 'none (empty database)'}; latest available: {head}")

    if check_only:
        if current != head:
            return fail(8, "Database is behind. Run scripts/dev/init-database.ps1 (or init_db.py).")
    else:
        try:
            command.upgrade(cfg, "head")
        except Exception as exc:  # noqa: BLE001 - report clearly, never a raw traceback
            return fail(6, f"Migration failed: {exc.__class__.__name__}. No data was deleted.")

    engine = create_engine(raw, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as conn:
            tables = set(inspect(conn).get_table_names())
            final = MigrationContext.configure(conn).get_current_revision()
    finally:
        engine.dispose()
    missing = REQUIRED_TABLES - tables
    if missing:
        return fail(7, f"Missing tables: {', '.join(sorted(missing))}")
    print(f"OK: revision {final} (head), {len(REQUIRED_TABLES)} required tables present.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
