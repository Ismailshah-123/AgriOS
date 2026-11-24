"""Project-local PostgreSQL for development (optional alternative to an existing server).

    uv run python scripts/local_db.py start    # create (first time) + start + create db
    uv run python scripts/local_db.py status
    uv run python scripts/local_db.py stop

* Data: backend/var/dev-postgres (git-ignored). Port 54330, listens on 127.0.0.1 only.
* Authentication: scram-sha-256 with a random password generated on first start. The
  password is written ONLY into backend/.env as DATABASE_URL, and only if DATABASE_URL is
  not already set (an existing configuration is never overwritten).
* Never touches any other PostgreSQL server or database. Never deletes data.
"""

import secrets
import subprocess  # noqa: S404 - fixed local tool invocations
import sys
import tempfile
from pathlib import Path

import psycopg
from env_file import read, set_missing
from pg_tools import find_bin

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "var" / "dev-postgres"
LOG_FILE = ROOT / "var" / "dev-postgres.log"
PORT = 54330
USER = "agrios"
DB_NAME = "agrios"


def running() -> bool:
    if not (DATA_DIR / "PG_VERSION").exists():
        return False
    res = subprocess.run(
        [find_bin("pg_ctl"), "-D", str(DATA_DIR), "status"],
        capture_output=True,
        check=False,
    )
    return res.returncode == 0


def _password_from_env() -> str | None:
    url = read().get("DATABASE_URL", "")
    if f"@127.0.0.1:{PORT}/" in url and url.startswith(f"postgresql+psycopg://{USER}:"):
        return url.split(":", 2)[2].split("@", 1)[0]
    return None


def init_cluster() -> str:
    password = secrets.token_urlsafe(24)
    DATA_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".pw", dir=DATA_DIR.parent) as fh:
        fh.write(password)
        pwfile = fh.name
    try:
        subprocess.run(
            [
                find_bin("initdb"),
                "-D",
                str(DATA_DIR),
                "-U",
                USER,
                "--pwfile",
                pwfile,
                "-A",
                "scram-sha-256",
                "-E",
                "UTF8",
                "--no-instructions",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    finally:
        Path(pwfile).unlink(missing_ok=True)
    with (DATA_DIR / "postgresql.conf").open("a", encoding="utf-8") as f:
        f.write(f"\nlisten_addresses = '127.0.0.1'\nport = {PORT}\n")
    return password


def start() -> int:
    fresh = not (DATA_DIR / "PG_VERSION").exists()
    if fresh and "DATABASE_URL" in read():
        print("backend/.env already has DATABASE_URL; not creating a local cluster over it.")
        print("Remove that line first if you really want the project-local database.")
        return 1
    password = init_cluster() if fresh else _password_from_env()
    if password is None:
        print("Local cluster exists but backend/.env does not point at it; leaving it alone.")
        return 1
    if not running():
        subprocess.run(
            [find_bin("pg_ctl"), "-D", str(DATA_DIR), "-l", str(LOG_FILE), "-w", "start"],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    with psycopg.connect(
        host="127.0.0.1",
        port=PORT,
        user=USER,
        password=password,
        dbname="postgres",
        autocommit=True,
    ) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,)).fetchone():
            conn.execute(f'CREATE DATABASE "{DB_NAME}" OWNER "{USER}"')
    if fresh:
        set_missing(
            {"DATABASE_URL": f"postgresql+psycopg://{USER}:{password}@127.0.0.1:{PORT}/{DB_NAME}"}
        )
        print("Created project-local PostgreSQL; DATABASE_URL written to backend/.env.")
    print(f"Local PostgreSQL running on 127.0.0.1:{PORT} (database '{DB_NAME}').")
    return 0


def stop() -> int:
    if running():
        subprocess.run(
            [find_bin("pg_ctl"), "-D", str(DATA_DIR), "-w", "stop", "-m", "fast"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    print("Local PostgreSQL stopped.")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "start":
        sys.exit(start())
    if cmd == "stop":
        sys.exit(stop())
    print("running" if running() else "stopped")
