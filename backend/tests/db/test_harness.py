"""Proves the database test harness is isolated and migrations run."""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

pytestmark = pytest.mark.db


def test_connected_to_a_test_database(migrated_engine: Engine) -> None:
    with migrated_engine.connect() as conn:
        name = conn.execute(text("SELECT current_database()")).scalar_one()
    assert "test" in name


def test_session_changes_are_rolled_back(db_session: Session) -> None:
    db_session.execute(text("CREATE TABLE _harness_probe (id int)"))
    db_session.flush()
    # The table exists inside the test's transaction...
    assert db_session.execute(text("SELECT to_regclass('_harness_probe')")).scalar_one()


def test_previous_test_left_nothing_behind(db_session: Session) -> None:
    assert db_session.execute(text("SELECT to_regclass('_harness_probe')")).scalar_one() is None
