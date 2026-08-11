from pathlib import Path

from app.ingestion.core_builder import build_staging_batch


def _write(tmp_path: Path, name: str, text: str) -> str:
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def test_staging_batch_tags_core_kb_id(tmp_path):
    path = _write(tmp_path, "report.txt", "Fitness apps grew 21% YoY.\n\nCompetitor engagement rose too.")
    chunks = build_staging_batch([path], target_version=1)
    assert chunks
    assert all(c.kb_id == "core:market-intel@v1:staging" for c in chunks)


def test_staging_batch_escalates_beyond_l1(tmp_path):
    long_paragraph = " ".join(["Fitness category benchmark data point."] * 60)  # well over l3_min_chars
    path = _write(tmp_path, "long.txt", long_paragraph)
    chunks = build_staging_batch([path], target_version=1)
    assert any(c.strategy in ("L2", "L3") for c in chunks)


def test_staging_batch_skips_unparseable_source(tmp_path):
    good = _write(tmp_path, "good.txt", "Real content here.")
    missing = str(tmp_path / "does-not-exist.txt")
    chunks = build_staging_batch([missing, good], target_version=1)
    assert len(chunks) >= 1
    assert all(c.doc_id != "" for c in chunks)
