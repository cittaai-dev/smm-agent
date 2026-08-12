from app.domain.chunk import Chunk
from app.ingestion.parse import parse_by_type
from app.ingestion.router import route_and_chunk
from app.ingestion.validators import validate_batch


def build_staging_batch(source_paths: list[str], target_version: int) -> list[Chunk]:
    """Second pipeline, not a fork (dual-kb.md): reuses ingestion/parse.py and
    ingestion/router.py + validators.py unchanged, only the ladder differs
    (L0-L3 here vs. Step 2's L0-L1). One doc's parse failure degrades that
    doc only (P5), same discipline as workers/ingest.py's ingest_file.
    """
    staging_kb_id = f"core:market-intel@v{target_version}:staging"
    chunks: list[Chunk] = []

    for path in source_paths:
        try:
            blocks = parse_by_type(path, source_kind="market_research")
        except Exception:  # noqa: BLE001, S112 -- P5: one bad source degrades, never aborts the batch
            continue

        non_empty = [b for b in blocks if b.text.strip()]
        if not non_empty:
            continue

        doc_id = _doc_id_from_path(path, staging_kb_id)
        batch = route_and_chunk(doc_id, staging_kb_id, non_empty, ladder="L0-L3")
        if not all(r.passed for r in validate_batch(batch)):
            # C6: degrade the whole doc's batch to L0 rather than drop it.
            batch = route_and_chunk(doc_id, staging_kb_id, non_empty, force_l0=True, ladder="L0-L3")
        chunks.extend(batch)

    return chunks


def _doc_id_from_path(path: str, kb_id: str) -> str:
    import hashlib

    return f"doc-{hashlib.sha256(f'{kb_id}:{path}'.encode()).hexdigest()[:12]}"
