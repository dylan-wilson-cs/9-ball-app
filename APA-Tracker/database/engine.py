"""Database engine construction, shared by every scheduler entry point.

Exists because each job used to build its own engine with
``create_engine(f"sqlite:///{path}")`` and nothing created the directory the
path points into. ``data/`` is gitignored and absent from a fresh clone, so
the first run of any job died with "unable to open database file" before
doing any work -- the same one-line gap repeated in three places.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine, create_engine, event, inspect, text

from database.models import Base

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = "data/apa_tracker.db"


class StaleSchemaError(RuntimeError):
    """The database file predates the current models and lacks columns."""


def check_schema(engine: Engine) -> list[str]:
    """Return descriptions of columns the models expect but the file lacks.

    ``Base.metadata.create_all`` creates missing TABLES but never alters
    existing ones, so a database written by an older build keeps its old
    columns and the first insert fails with a bare "no such column: ...".
    There is no migration tooling here and none is warranted: every row is
    re-fetchable from the API, so the fix is to delete the file.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing: list[str] = []

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # create_all will make it
        present = {column["name"] for column in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in present:
                missing.append(f"{table_name}.{column.name}")
    return missing


def add_missing_columns(engine: Engine) -> list[str]:
    """Add every column the models expect but the file lacks, in place.

    SQLite supports ``ALTER TABLE ... ADD COLUMN`` for a nullable column (or
    one with a default), which covers every column this project has ever
    added. The production database is the permanent career archive and is
    copied into staging at the start of each refresh, so "delete the file"
    is no longer an acceptable fix for a widened model. Returns the
    descriptions of the columns added. Raises StaleSchemaError for a
    column that cannot be added this way.
    """
    missing = set(check_schema(engine))
    if not missing:
        return []
    added: list[str] = []
    with engine.begin() as conn:
        for table_name, table in Base.metadata.tables.items():
            for column in table.columns:
                key = f"{table_name}.{column.name}"
                if key not in missing:
                    continue
                if not column.nullable and column.default is None and column.server_default is None:
                    raise StaleSchemaError(
                        f"{key} is NOT NULL with no default and cannot be added to an "
                        f"existing table in place; rebuild the database from the API."
                    )
                type_sql = column.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN "{column.name}" {type_sql}'))
                added.append(key)
    if added:
        logger.info("Schema updated in place: added %s", ", ".join(added))
    return added


def _enable_foreign_keys(dbapi_connection, connection_record) -> None:
    """SQLite does not enforce foreign keys unless told to, per connection
    -- it's off by default even with FKs declared in the schema. This
    project already hit the real cost of that once: PlayerMatch.match_id
    pointed at a Match row that didn't exist (a units mix-up -- APA's own
    match id stored where the internal primary key belonged) and nothing
    ever raised; `.match` just silently returned None (see
    database/ingest.py::_resolve_match_pk's docstring, and
    tests/test_match_detail_fixture.py::test_the_foreign_key_actually_resolves,
    the regression test for it). Enforcement would have turned that into a
    loud IntegrityError at insert time instead of a silent orphan.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys = ON")
    cursor.close()


def create_db_engine(config: dict, create_tables: bool = True) -> Engine:
    """Return an engine for the configured SQLite file, creating what's missing.

    Creates the parent directory and (unless told otherwise) the tables, so a
    first run on a clean checkout works rather than failing on a missing
    directory. Every connection this engine opens gets PRAGMA foreign_keys
    = ON (see _enable_foreign_keys) -- SQLite ignores that pragma unless
    it's set on the specific connection doing the writing, so this has to
    be a connect-event hook, not a one-time statement.
    """
    db_path = Path((config.get("database") or {}).get("path") or DEFAULT_DB_PATH)
    if db_path.parent and not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Created database directory %s", db_path.parent)

    engine = create_engine(f"sqlite:///{db_path}")
    event.listen(engine, "connect", _enable_foreign_keys)
    if create_tables:
        Base.metadata.create_all(engine)
        add_missing_columns(engine)
        missing = check_schema(engine)
        if missing:
            raise StaleSchemaError(
                f"{db_path} is missing {len(missing)} column(s) that could not be "
                f"added in place: {', '.join(missing)}. Rebuild it from the API."
            )
    return engine
