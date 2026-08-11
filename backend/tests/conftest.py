from pathlib import Path

import pytest

from app.domain.claim import ClaimDraft
from app.domain.retrieval import RetrievalPlan
from app.infra.db import get_session


@pytest.fixture(autouse=True)
def clean_db():
    with get_session() as session:
        session.execute("TRUNCATE deliverable, chunk, document_registry CASCADE")
        session.commit()
    yield


@pytest.fixture
def sample_file(tmp_path: Path) -> str:
    path = tmp_path / "brand.txt"
    path.write_text(
        "Acme Roasters is a specialty coffee brand founded in 2019, selling small-batch "
        "beans direct to consumers online.\n\n"
        "The brand operates two retail locations and ships nationwide, with a focus on "
        "single-origin beans sourced directly from growers."
    )
    return str(path)


@pytest.fixture
def fake_plan(monkeypatch):
    """Patches call_plan so no real LLM call happens. The sub-query text doesn't
    matter for correctness here — search_dense returns all chunks for a KB this
    small regardless of query."""

    def _fake(section: str, brand_id: str) -> RetrievalPlan:
        return RetrievalPlan(sub_queries=["brand overview"], k_per_query=8)

    monkeypatch.setattr("app.orchestration.llm.call_plan", _fake)


@pytest.fixture
def fake_synthesize_grounded(monkeypatch, fake_plan):
    """Synthesize always cites a real chunk_id from the retrieved context — the
    happy path, no repair needed."""

    def _fake(section: str, context):
        chunk = context.chunks[0]
        return [ClaimDraft(section=section, text="Acme Roasters sells specialty coffee.", chunk_id=chunk.chunk_id)]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake)


@pytest.fixture
def fake_synthesize_fabricated(monkeypatch, fake_plan):
    """Synthesize cites a chunk_id that does not exist in the retrieved context —
    forces the verifier to reject and the repair path to fire."""

    def _fake(section: str, context):
        return [ClaimDraft(section=section, text="Acme Roasters sells specialty coffee.", chunk_id="not-a-real-chunk-id")]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake)

    def _fake_repair(claims, context):
        chunk = context.chunks[0]
        return [ClaimDraft(section=c.section, text=c.text, chunk_id=chunk.chunk_id) for c in claims]

    monkeypatch.setattr("app.orchestration.llm.call_repair", _fake_repair)


@pytest.fixture
def fake_synthesize_empty(monkeypatch, fake_plan):
    """Synthesize finds no evidence worth claiming anything from -- the
    honest-empty-section path (dev_guidelines.md §11), as opposed to a
    fabricated citation."""

    def _fake(section: str, context):
        return []

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake)
