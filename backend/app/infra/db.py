from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from app.infra.settings import db_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(db_settings.database_url, pool_pre_ping=True)
    return _engine


class Session:
    """Thin wrapper so call sites can write session.execute("SELECT ...", {...})
    against raw SQL, matching docs/implement/step1_foundation.md's style, without
    every call site remembering to wrap the string in text()."""

    def __init__(self, conn: Connection):
        self._conn = conn

    def execute(self, sql: str, params: dict[str, Any] | None = None):
        return self._conn.execute(text(sql), params or {})

    def commit(self) -> None:
        self._conn.commit()


@contextmanager
def get_session() -> Iterator[Session]:
    conn = get_engine().connect()
    try:
        yield Session(conn)
    finally:
        conn.close()
