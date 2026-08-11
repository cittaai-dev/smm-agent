from app.domain.chunk import Chunk
from app.infra.db import get_session
from app.infra.settings import rerank_settings
from app.retrieval import rerank as rerank_module


def _chunk(cid: str, text: str) -> Chunk:
    return Chunk(chunk_id=cid, kb_id="run:x", doc_id="d1", block_span=(0, 0), text=text)


def test_rerank_orders_by_model_score_descending(monkeypatch):
    monkeypatch.setattr(rerank_settings, "enabled", True)
    scores = {"low": 0.1, "high": 0.9, "mid": 0.5}
    monkeypatch.setattr(rerank_module, "_model_predict", lambda query, text: scores[text])
    chunks = [_chunk("low", "low"), _chunk("high", "high"), _chunk("mid", "mid")]

    result = rerank_module.rerank(chunks, "some query")

    assert [c.chunk_id for c in result] == ["high", "mid", "low"]


def test_rerank_disabled_returns_chunks_unchanged(monkeypatch):
    monkeypatch.setattr(rerank_settings, "enabled", False)
    calls = []
    monkeypatch.setattr(rerank_module, "_model_predict", lambda query, text: calls.append(1) or 1.0)
    chunks = [_chunk("a", "a"), _chunk("b", "b")]

    result = rerank_module.rerank(chunks, "q")

    assert [c.chunk_id for c in result] == ["a", "b"]
    assert calls == []


def test_rerank_empty_list_short_circuits(monkeypatch):
    calls = []
    monkeypatch.setattr(rerank_module, "_model_predict", lambda query, text: calls.append(1) or 1.0)
    assert rerank_module.rerank([], "q") == []
    assert calls == []


def test_rerank_cache_hit_avoids_recompute(monkeypatch):
    monkeypatch.setattr(rerank_settings, "enabled", True)
    call_count = {"n": 0}

    def _fake_predict(query: str, text: str) -> float:
        call_count["n"] += 1
        return 0.5

    monkeypatch.setattr(rerank_module, "_model_predict", _fake_predict)
    rerank_module._in_process_cache.clear()
    chunks = [_chunk("a", "text a")]

    rerank_module.rerank(chunks, "same query")
    calls_after_first = call_count["n"]
    rerank_module.rerank(chunks, "same query")

    assert call_count["n"] == calls_after_first  # in-process cache hit, no new model call


def test_rerank_cache_persists_across_in_process_cache_clears(monkeypatch):
    # Simulates a cache hit surviving a process restart -- clear the
    # process-local dict but leave the Postgres rerank_cache table alone.
    monkeypatch.setattr(rerank_settings, "enabled", True)
    call_count = {"n": 0}

    def _fake_predict(query: str, text: str) -> float:
        call_count["n"] += 1
        return 0.7

    monkeypatch.setattr(rerank_module, "_model_predict", _fake_predict)
    rerank_module._in_process_cache.clear()
    chunks = [_chunk("a", "text a")]

    rerank_module.rerank(chunks, "same query")
    assert call_count["n"] == 1

    rerank_module._in_process_cache.clear()
    rerank_module.rerank(chunks, "same query")

    assert call_count["n"] == 1  # DB cache hit, still no new model call


def test_rerank_cache_row_actually_persisted(monkeypatch):
    monkeypatch.setattr(rerank_settings, "enabled", True)
    monkeypatch.setattr(rerank_module, "_model_predict", lambda query, text: 0.42)
    rerank_module._in_process_cache.clear()
    chunks = [_chunk("a", "text a")]

    rerank_module.rerank(chunks, "persisted query")

    with get_session() as session:
        row = session.execute(
            "SELECT score FROM rerank_cache WHERE query_hash = :qh AND chunk_id = 'a'",
            {"qh": rerank_module.query_hash("persisted query")},
        ).mappings().first()
    assert row["score"] == 0.42
