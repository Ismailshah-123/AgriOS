"""Admin CLI: change a user's role (farmer | expert | admin). Audited.

uv run python scripts/set_role.py <email> <role>

There is no admin UI for roles yet; this is how an agronomist account becomes an expert for
the FR12 review queue. Uses DATABASE_URL from backend/.env (never prints it).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.audit import service as audit  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.identity.models import User, UserRole  # noqa: E402


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] not in {r.value for r in UserRole}:
        print(__doc__)
        return 2
    email, role = argv[0].strip().lower(), UserRole(argv[1])
    engine = create_engine(get_settings().database_url.get_secret_value())
    with Session(engine) as db:
        user = db.scalar(select(User).where(func.lower(User.email) == email))
        if user is None:
            print(f"No user with email {email}")
            return 1
        before = user.role
        user.role = role
        audit.record(
            db,
            action="user.role_changed",
            entity="user",
            entity_id=user.id,
            meta={"from": before.value, "to": role.value, "via": "scripts/set_role.py"},
        )
        db.commit()
        print(f"{email}: {before.value} -> {role.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
