from app.infra.db import get_session


def get_active_core_version() -> str | None:
    """The promoted (not staging) kb_id with the highest version, or None if
    nothing has ever been promoted. This is what core_kb_available() and the
    core_only/bridge runners check instead of the Step 2 hardcoded False."""
    with get_session() as session:
        row = session.execute(
            "SELECT kb_id FROM kb_version WHERE status = 'promoted' ORDER BY version DESC LIMIT 1"
        ).first()
    return row[0] if row else None
