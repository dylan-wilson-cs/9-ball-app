"""Stale-database detection.

`Base.metadata.create_all` creates missing tables but never ALTERS existing
ones. A database written before columns like matches.week or players.ppm
existed keeps its old shape, and the first insert dies with a bare
"sqlite3.OperationalError: no such column". These tests build a genuinely
old-shaped database and assert the failure is caught up front, with the fix
spelled out.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from database.engine import StaleSchemaError, add_missing_columns, check_schema, create_db_engine
from database.models import Base


def _make_stale_db(path):
    """A database with the right tables but an older, narrower `matches`."""
    engine = create_engine(f"sqlite:///{path}")
    with engine.begin() as conn:
        # The Match model as it was before scores and flags were added.
        conn.execute(text("""
            CREATE TABLE matches (
                id INTEGER NOT NULL PRIMARY KEY,
                external_id VARCHAR NOT NULL UNIQUE,
                home_team_id VARCHAR,
                away_team_id VARCHAR,
                home_team_name VARCHAR,
                away_team_name VARCHAR,
                location VARCHAR,
                match_date VARCHAR,
                status VARCHAR
            )
        """))
    engine.dispose()


class TestCheckSchema:
    def test_a_current_database_reports_nothing_missing(self, tmp_path):
        engine = create_engine(f"sqlite:///{tmp_path / 'fresh.db'}")
        Base.metadata.create_all(engine)
        assert check_schema(engine) == []

    def test_missing_columns_are_named(self, tmp_path):
        path = tmp_path / "stale.db"
        _make_stale_db(path)
        engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)  # adds the other tables, leaves matches alone

        missing = check_schema(engine)
        assert "matches.week" in missing
        assert "matches.home_score" in missing
        assert "matches.is_bye" in missing
        # Tables it created fresh are complete.
        assert not any(m.startswith("players.") for m in missing)

    def test_an_absent_table_is_not_reported_as_missing_columns(self, tmp_path):
        """create_all will make it; that is not a stale-schema problem."""
        engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
        assert check_schema(engine) == []


class TestCreateDbEngineWidensStaleFiles:
    def test_missing_nullable_columns_are_added_in_place(self, tmp_path):
        """The production database is the permanent career archive and is
        copied into staging at the start of every refresh, so a widened
        model must not demand deleting it. Every column this project adds
        is nullable, which SQLite can ALTER TABLE ... ADD COLUMN in place."""
        path = tmp_path / "old.db"
        _make_stale_db(path)

        engine = create_db_engine({"database": {"path": str(path)}})

        assert check_schema(engine) == []
        with engine.begin() as conn:
            conn.execute(text(
                "INSERT INTO matches (external_id, week, home_score, is_bye) VALUES ('M1', 3, 12.0, 0)"
            ))
            row = conn.execute(text("SELECT week, home_score FROM matches WHERE external_id = 'M1'")).one()
        assert tuple(row) == (3, 12.0)

    def test_add_missing_columns_reports_what_it_added_and_is_idempotent(self, tmp_path):
        path = tmp_path / "old.db"
        _make_stale_db(path)
        engine = create_engine(f"sqlite:///{path}")
        Base.metadata.create_all(engine)

        added = add_missing_columns(engine)
        assert "matches.week" in added and "matches.home_score" in added
        assert add_missing_columns(engine) == []

    def test_a_fresh_path_is_fine(self, tmp_path):
        engine = create_db_engine({"database": {"path": str(tmp_path / "sub" / "new.db")}})
        assert check_schema(engine) == []

    def test_running_twice_on_the_same_file_is_fine(self, tmp_path):
        config = {"database": {"path": str(tmp_path / "twice.db")}}
        create_db_engine(config)
        create_db_engine(config)  # must not trip its own check
