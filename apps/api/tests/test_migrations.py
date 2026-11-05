"""The Alembic migrations build exactly the schema the SQLModel tables describe."""

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlmodel import SQLModel

import ishi.db.models  # noqa: F401  (registers the tables)
from ishi.db.session import get_engine, migrate


def test_migrations_match_models(tmp_path: Path) -> None:
    db = tmp_path / "schema.db"
    migrate(db)
    with get_engine(db).connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), SQLModel.metadata)
    assert diff == []
