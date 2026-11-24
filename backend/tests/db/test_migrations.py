"""Migrations are reversible, match the ORM models, and enforce append-only audit."""

import uuid

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.exc import DBAPIError

from alembic import command
from app.db import models_registry  # noqa: F401 - full metadata
from app.db.base import Base
from tests.support import alembic_config, reset_schema

pytestmark = pytest.mark.db


def test_upgrade_downgrade_upgrade_on_empty_database(db_url: str) -> None:
    engine = create_engine(db_url)
    cfg = alembic_config(db_url)
    try:
        reset_schema(engine)
        command.upgrade(cfg, "head")
        assert {"users", "refresh_tokens", "audit_events"} <= set(inspect(engine).get_table_names())
        command.downgrade(cfg, "base")
        assert set(inspect(engine).get_table_names()) <= {"alembic_version"}
        command.upgrade(cfg, "head")  # leave the schema at head for the other tests
    finally:
        engine.dispose()


def test_models_match_migrations(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    assert diff == [], f"ORM models and migrations differ: {diff}"


def _insert_event(conn: object) -> uuid.UUID:
    event_id = uuid.uuid4()
    conn.execute(  # type: ignore[attr-defined]
        text("INSERT INTO audit_events (id, action, entity) VALUES (:id, 'x.test', 'thing')"),
        {"id": event_id},
    )
    return event_id


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET action = 'tampered' WHERE id = :id",
        "DELETE FROM audit_events WHERE id = :id",
    ],  # fmt: skip
    ids=["update", "delete"],
)
def test_audit_events_are_append_only(migrated_engine: Engine, statement: str) -> None:
    with migrated_engine.connect() as conn, conn.begin() as tx:
        event_id = _insert_event(conn)
        with pytest.raises(DBAPIError, match="append-only"):
            conn.execute(text(statement), {"id": event_id})
        tx.rollback()


def test_deleting_a_user_keeps_audit_rows_with_null_actor(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn, conn.begin() as tx:
        uid = uuid.uuid4()
        conn.execute(
            text(
                "INSERT INTO users (id, email, password_hash, full_name, role, locale) "
                "VALUES (:id, 'gone@example.com', 'h', 'Gone', 'farmer', 'en')"
            ),
            {"id": uid},
        )
        conn.execute(
            text(
                "INSERT INTO audit_events (id, actor_id, action, entity) VALUES "
                "(gen_random_uuid(), :uid, 'user.registered', 'user')"
            ),  # fmt: skip
            {"uid": uid},
        )
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": uid})
        actor = conn.execute(
            text("SELECT actor_id FROM audit_events WHERE action = 'user.registered'")
        ).scalar_one()
        assert actor is None
        tx.rollback()
