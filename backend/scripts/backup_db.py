"""Backup the AgriOS database with pg_dump (custom format) before a schema change.

uv run python scripts/backup_db.py [out_dir]   (default: ../var/backups)

Reads DATABASE_URL from backend/.env; the password goes to pg_dump via PGPASSWORD and is
never printed. Never overwrites: the file name carries a timestamp.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from scripts.pg_tools import find_bin  # noqa: E402


def main(argv: list[str]) -> int:
    url = make_url(get_settings().database_url.get_secret_value())
    out_dir = Path(argv[0]) if argv else Path(__file__).resolve().parents[2] / "var" / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{url.database}_{datetime.now():%Y%m%d_%H%M%S}.dump"
    if out.exists():
        print(f"refusing to overwrite {out}")
        return 1
    env = {**os.environ, "PGPASSWORD": url.password or ""}
    cmd = [find_bin("pg_dump"), "-h", url.host or "127.0.0.1", "-p", str(url.port or 5432),
           "-U", url.username or "", "-d", url.database or "", "-Fc", "-f", str(out)]  # fmt: skip
    res = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
    if res.returncode != 0:
        print(res.stderr.strip())
        return res.returncode
    print(f"backup written: {out} ({out.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
