"""Throwaway PostgreSQL cluster for the test suite (no Docker, no real credentials).

Creates an isolated cluster under backend/var/test-postgres (git-ignored), listening on
127.0.0.1 only, with a database named `agrios_test`. It never touches any other
PostgreSQL server on the machine. Authentication is `trust` on loopback because the
cluster holds only disposable test data; do not reuse it for anything else.

Usage (from backend/):
    uv run python scripts/test_db.py start   # init (first time) + start + create db
    uv run python scripts/test_db.py url     # print TEST_DATABASE_URL
    uv run python scripts/test_db.py stop
    uv run python scripts/test_db.py reset agrios_e2e_test   # fresh named db (e2e)
    uv run python scripts/test_db.py url agrios_e2e_test
Requires PostgreSQL server binaries (initdb, pg_ctl) on PATH or in PG_BIN.
Alternative with Docker: `docker compose --profile test up -d db_test` (see docker-compose.yml).
"""

import os
import subprocess  # noqa: S404 - runs local PostgreSQL tools with fixed arguments
import sys
from pathlib import Path

import psycopg
from pg_tools import find_bin

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "var" / "test-postgres"
LOG_FILE = ROOT / "var" / "test-postgres.log"
PORT = int(os.environ.get("TEST_PG_PORT", "54329"))
USER = "agrios_test"
DB_NAME = "agrios_test"
URL = f"postgresql+psycopg://{USER}@127.0.0.1:{PORT}/{DB_NAME}"


def url_for(name: str) -> str:
    return f"postgresql+psycopg://{USER}@127.0.0.1:{PORT}/{name}"


def reset(name: str) -> None:
    """Drop and recreate a named database inside the throwaway cluster."""
    if "test" not in name:
        sys.exit("Refusing: database name must contain 'test'.")
    start()
    with psycopg.connect(
        f"host=127.0.0.1 port={PORT} user={USER} dbname=postgres", autocommit=True
    ) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        conn.execute(f'CREATE DATABASE "{name}"')
    print(f"Reset {name}")


def _bin(name: str) -> str:
    return find_bin(name)


def _run(*args: str) -> None:
    subprocess.run(args, check=True)


def start() -> None:
    if not (DATA_DIR / "PG_VERSION").exists():
        DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
        _run(
            _bin("initdb"),
            "-D",
            str(DATA_DIR),
            "-U",
            USER,
            "-A",
            "trust",
            "-E",
            "UTF8",
            "--no-instructions",
        )
        with (DATA_DIR / "postgresql.conf").open("a", encoding="utf-8") as f:
            # Loopback only; speed settings are safe because the data is disposable.
            f.write(f"\nlisten_addresses = '127.0.0.1'\nport = {PORT}\n")
            f.write("fsync = off\nsynchronous_commit = off\nfull_page_writes = off\n")
    if not _running():
        # Detach from our stdio: on Windows the server otherwise inherits the pipe
        # handles and callers piping our output never see EOF. Errors go to LOG_FILE.
        subprocess.run(
            [_bin("pg_ctl"), "-D", str(DATA_DIR), "-l", str(LOG_FILE), "-w", "start"],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    with psycopg.connect(
        f"host=127.0.0.1 port={PORT} user={USER} dbname=postgres", autocommit=True
    ) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_NAME,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{DB_NAME}"')
    print(f"Test database ready.\nTEST_DATABASE_URL={URL}")


def _running() -> bool:
    if not DATA_DIR.exists():
        return False
    res = subprocess.run(
        [_bin("pg_ctl"), "-D", str(DATA_DIR), "status"], capture_output=True, check=False
    )
    return res.returncode == 0


def stop() -> None:
    if _running():
        _run(_bin("pg_ctl"), "-D", str(DATA_DIR), "-w", "stop", "-m", "fast")
    print("Test database stopped.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd == "url":
        print(url_for(sys.argv[2]) if len(sys.argv) > 2 else URL)
    elif cmd == "reset" and len(sys.argv) > 2:
        reset(sys.argv[2])
    else:
        print("running" if _running() else "stopped")
