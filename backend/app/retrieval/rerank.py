import hashlib

from app.domain.chunk import Chunk
from app.infra.db import get_session
from app.infra.settings import rerank_settings

_model = None
# Two cache layers, different purposes: this dict is process-local and cheap
# but doesn't survive a restart or share across workers; rerank_cache
# (Postgres, migration 0005) does. Keyed explicitly by (query_hash, chunk_id)
# rather than via functools.lru_cache on the scoring function itself, so the
# key doesn't include full chunk text.
_in_process_cache: dict[tuple[str, str], float] = {}


def _get_model():
    # Loaded lazily, not at import time -- a cross-encoder is a genuinely
    # heavy, possibly-first-run-download dependency, and importing this module
    # (e.g. transitively, from hybrid.py) must never force that cost on a
    # process that never actually calls rerank().
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        _model = CrossEncoder(rerank_settings.model_name)
    return _model


def _model_predict(query: str, text: str) -> float:
    """Isolated on its own so tests can monkeypatch this one function instead
    of needing the real ~1GB model."""
    return float(_get_model().predict([(query, text)])[0])


def query_hash(query: str) -> str:
    return hashlib.sha256(query.encode()).hexdigest()


def _cached_score(qh: str, chunk_id: str) -> float | None:
    with get_session() as session:
        row = session.execute(
            "SELECT score FROM rerank_cache WHERE query_hash = :qh AND chunk_id = :cid",
            {"qh": qh, "cid": chunk_id},
        ).mappings().first()
    return row["score"] if row else None


def _store_score(qh: str, chunk_id: str, score: float) -> None:
    with get_session() as session:
        session.execute(
            """INSERT INTO rerank_cache (query_hash, chunk_id, score) VALUES (:qh, :cid, :score)
               ON CONFLICT (query_hash, chunk_id) DO NOTHING""",
            {"qh": qh, "cid": chunk_id, "score": score},
        )
        session.commit()


def _score(qh: str, chunk_id: str, query: str, text: str) -> float:
    key = (qh, chunk_id)
    if key in _in_process_cache:
        return _in_process_cache[key]
    cached = _cached_score(qh, chunk_id)
    if cached is not None:
        _in_process_cache[key] = cached
        return cached
    score = _model_predict(query, text)
    _store_score(qh, chunk_id, score)
    _in_process_cache[key] = score
    return score


def rerank(chunks: list[Chunk], query: str) -> list[Chunk]:
    """Deterministic, cacheable, not a call site (P2) -- a cross-encoder score
    is not generative reasoning, same status as embedding or dense search."""
    if not chunks:
        return chunks
    if not rerank_settings.enabled:
        return chunks
    qh = query_hash(query)
    scored = [(c, _score(qh, c.chunk_id, query, c.text)) for c in chunks]
    return [c for c, _ in sorted(scored, key=lambda pair: -pair[1])]
