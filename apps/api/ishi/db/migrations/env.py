"""Alembic environment. The engine is passed in by `ishi.db.session.migrate` (or built from
settings when run via the alembic CLI)."""

from alembic import context
from sqlmodel import SQLModel

import ishi.db.models  # noqa: F401  (registers tables on SQLModel.metadata)

config = context.config
target_metadata = SQLModel.metadata


def run_migrations_online() -> None:
    engine = config.attributes.get("engine")
    if engine is None:
        from ishi.config import get_settings
        from ishi.db.session import get_engine

        engine = get_engine(get_settings().db_path)
    with engine.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )
        with context.begin_transaction():
            context.run_migrations()
        connection.commit()


run_migrations_online()
