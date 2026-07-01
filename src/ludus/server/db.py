"""Database engine and session management (SQLModel + SQLite)."""

from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from ludus.server.config import get_settings

_settings = get_settings()

# check_same_thread=False is required for SQLite under a threaded ASGI server.
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}

engine = create_engine(_settings.database_url, echo=False, connect_args=_connect_args)


def create_db_and_tables() -> None:
    """Create all tables. Idempotent; safe to call on every startup.

    NOTE: no migrations (Alembic) yet — see the plan's "out of scope" section.
    """
    # Import models so they register on SQLModel.metadata before create_all.
    from ludus.server import db_models  # noqa: F401

    _settings.ensure_dirs()
    SQLModel.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped DB session."""
    with Session(engine) as session:
        yield session
