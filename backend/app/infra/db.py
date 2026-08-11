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
def get_session(kb_id: str | None = None) -> Iterator[Session]:
    """Every call site touching chunk/document_registry/source_file for a
    single brand's data should pass kb_id (step5_trust_boundary.md Part A).
    `SET LOCAL ROLE brand_workspace_role` (migration 0008) drops this
    connection's superuser/table-owner RLS bypass for the rest of the
    transaction, so the policy actually applies -- not just declared. Callers
    that legitimately span brands (TTL sweep, Core promotion, admin routes)
    pass no kb_id and keep today's unscoped behavior; RLS is defense-in-depth
    on top of the app-layer check (api/deps.py), not a replacement for it."""
    conn = get_engine().connect()
    try:
        session = Session(conn)
        if kb_id:
            session.execute("SET LOCAL ROLE brand_workspace_role")
            # set_config(..., is_local=true), not a literal `SET LOCAL app.current_kb_id
            # = :kb` -- Postgres's SET grammar doesn't accept bind parameters, only
            # this function-call form does.
            session.execute("SELECT set_config('app.current_kb_id', :kb, true)", {"kb": kb_id})
        yield session
    finally:
        conn.close()
