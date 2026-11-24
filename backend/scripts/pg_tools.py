"""Shared helper: locate PostgreSQL server binaries (initdb, pg_ctl, pg_isready).

Search order: PG_BIN env var, PATH, then the standard Windows install folders
(newest version first). Used by test_db.py and local_db.py.
"""

import os
import shutil
import sys
from pathlib import Path


def find_bin(name: str) -> str:
    candidates = [Path(os.environ["PG_BIN"]) / name] if os.environ.get("PG_BIN") else []
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    windows_installs = Path("C:/Program Files/PostgreSQL").glob(f"*/bin/{name}.exe")
    candidates += sorted(windows_installs, reverse=True)
    for c in candidates:
        if c.exists() or c.with_suffix(".exe").exists():
            return str(c)
    sys.exit(f"{name} not found. Install PostgreSQL server binaries or set PG_BIN.")
