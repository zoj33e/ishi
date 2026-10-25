"""SQLite engine (WAL mode), Alembic migrations, request-scoped sessions and the single MVP user."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from alembic import command
from alembic.config import Config
from fastapi import Depends
from sqlalchemy import Engine, event, text
from sqlmodel import Session, create_engine, select

from ishi.config import get_settings
from ishi.db.models import User

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


@lru_cache
def get_engine(db_path: Path) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def migrate(db_path: Path) -> None:
    """Bring the database to the latest schema (`alembic upgrade head`)."""
    cfg = Config()
    cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
    cfg.attributes["engine"] = get_engine(db_path)
    command.upgrade(cfg, "head")


def db_ok(db_path: Path) -> bool:
    try:
        with get_engine(db_path).connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


def get_session() -> Iterator[Session]:
    """FastAPI dependency."""
    with Session(get_engine(get_settings().db_path)) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


def get_or_create_user(session: Session) -> User:
    """MVP has exactly one user, created on first use (D-011: multi-user is a later migration)."""
    user = session.exec(select(User)).first()
    if user is None:
        user = User(locale=get_settings().default_locale)
        session.add(user)
        session.commit()
        session.refresh(user)
    return user
