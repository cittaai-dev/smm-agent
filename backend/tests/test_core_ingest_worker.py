from app.infra.db import get_session
from app.workers.core_ingest import build_staging


def _write(tmp_path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def test_build_staging_stores_chunks_and_kb_version(tmp_path):
    path = _write(tmp_path, "report.txt", "Fitness apps grew 21% YoY across the category.")
    result = build_staging([path], target_version=1)
    assert "staged" in result

    with get_session() as session:
        version_row = session.execute(
            "SELECT status FROM kb_version WHERE kb_id = 'core:market-intel@v1:staging'"
        ).first()
        chunk_count = session.execute(
            "SELECT count(*) FROM chunk WHERE kb_id = 'core:market-intel@v1:staging'"
        ).scalar()
    assert version_row[0] == "staging"
    assert chunk_count >= 1


def test_build_staging_empty_sources_returns_early():
    result = build_staging([], target_version=2)
    assert result == "staged-empty"

    with get_session() as session:
        row = session.execute(
            "SELECT 1 FROM kb_version WHERE kb_id = 'core:market-intel@v2:staging'"
        ).first()
    assert row is None
