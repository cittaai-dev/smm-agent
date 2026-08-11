from pathlib import Path

import pytest

from app.domain.audience_persona import AudiencePersonaDraft
from app.domain.claim import ClaimDraft
from app.domain.retrieval import RetrievalPlan
from app.infra.settings import db_settings, rerank_settings

# Must happen before any test imports app.infra.db / calls get_session() --
# get_engine() lazily creates a module-global engine from db_settings.database_url
# on first use, so this override has to land before that first call. Without it,
# the autouse TRUNCATE below would hit the same database the dev server/worker
# use (this happened once already: running pytest wiped real ingested brand
# data). Create the DB once and point migrations at it:
#   docker exec infra-postgres-1 createdb -U postgres smm_test
#   TEST_DATABASE_URL=$TEST_DATABASE_URL DATABASE_URL=$TEST_DATABASE_URL \
#     .venv/bin/alembic upgrade head   # or just re-run alembic with DATABASE_URL=the test url
db_settings.database_url = db_settings.test_database_url

from app.infra.db import get_session


@pytest.fixture(autouse=True)
def disable_rerank_by_default():
    # Same reasoning as embeddings' offline fallback (infra/embeddings.py) --
    # the cross-encoder is a genuinely heavy, possibly-not-yet-downloaded
    # dependency, and the general test suite must stay runnable without it.
    # Tests of rerank.py itself explicitly re-enable this in their own scope.
    original = rerank_settings.enabled
    rerank_settings.enabled = False
    yield
    rerank_settings.enabled = original


@pytest.fixture(autouse=True)
def clean_db():
    with get_session() as session:
        session.execute(
            "TRUNCATE deliverable, chunk, document_registry, source_file, "
            "team_input, market_research_document, strategic_note, "
            "approval_gate, distribution_record, rerank_cache, "
            "brand_grant, api_key, brand, app_user, "
            "promotion_request, kb_version, golden_case, core_competitor_registry, "
            "approval_event, distribution_event, distribution_link, "
            "data_source_credential, market_segment, collection_job_status CASCADE"
        )
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

    def _fake(section: str, brand_id: str, cost_tracker=None) -> RetrievalPlan:
        return RetrievalPlan(sub_queries=["brand overview"], k_per_query=8)

    monkeypatch.setattr("app.orchestration.llm.call_plan", _fake)


@pytest.fixture
def fake_synthesize_grounded(monkeypatch, fake_plan):
    """Synthesize always cites a real chunk_id from the retrieved context — the
    happy path, no repair needed."""

    def _fake(section: str, context, cost_tracker=None):
        chunk = context.chunks[0]
        return [ClaimDraft(section=section, text="Acme Roasters sells specialty coffee.", chunk_id=chunk.chunk_id)]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake)


@pytest.fixture
def fake_synthesize_fabricated(monkeypatch, fake_plan):
    """Synthesize cites a chunk_id that does not exist in the retrieved context —
    forces the verifier to reject and the repair path to fire."""

    def _fake(section: str, context, cost_tracker=None):
        return [ClaimDraft(section=section, text="Acme Roasters sells specialty coffee.", chunk_id="not-a-real-chunk-id")]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake)

    def _fake_repair(claims, context, cost_tracker=None):
        chunk = context.chunks[0]
        return [ClaimDraft(section=c.section, text=c.text, chunk_id=chunk.chunk_id) for c in claims]

    monkeypatch.setattr("app.orchestration.llm.call_repair", _fake_repair)


@pytest.fixture
def fake_synthesize_fabricated_unrepairable(monkeypatch, fake_plan):
    """Synthesize fabricates a citation, and Repair's own attempt *also* fails
    to produce a resolvable chunk_id -- proves the bounded-retry half of P2/P5
    that fake_synthesize_fabricated's always-succeeds repair never exercises:
    a single repair attempt, then degrade, never a second try."""

    def _fake(section: str, context, cost_tracker=None):
        return [ClaimDraft(section=section, text="Acme Roasters sells specialty coffee.", chunk_id="not-a-real-chunk-id")]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake)

    def _fake_repair_still_fails(claims, context, cost_tracker=None):
        return [ClaimDraft(section=c.section, text=c.text, chunk_id="still-not-a-real-chunk-id") for c in claims]

    monkeypatch.setattr("app.orchestration.llm.call_repair", _fake_repair_still_fails)


@pytest.fixture
def fake_synthesize_with_personas(monkeypatch, fake_plan):
    """target_audience's combined claims+personas call site, happy path."""

    def _fake(section: str, context, cost_tracker=None):
        chunk = context.chunks[0]
        claims = [ClaimDraft(section=section, text="Acme Roasters targets busy professionals.", chunk_id=chunk.chunk_id)]
        personas = [
            AudiencePersonaDraft(
                section=section,
                name="Busy professional",
                pain_points=["No time to brew coffee well"],
                interests=["Convenience", "Quality"],
                chunk_ids=[chunk.chunk_id],
            )
        ]
        return claims, personas

    monkeypatch.setattr("app.orchestration.llm.call_synthesize_with_personas", _fake)


@pytest.fixture
def fake_synthesize_empty(monkeypatch, fake_plan):
    """Synthesize finds no evidence worth claiming anything from -- the
    honest-empty-section path (dev_guidelines.md §11), as opposed to a
    fabricated citation."""

    def _fake(section: str, context, cost_tracker=None):
        return []

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake)


@pytest.fixture
def fake_full_document_pipeline(monkeypatch, fake_plan):
    """Covers every LLM call site run_all_sections can reach for union and
    synthesis_only sections, so a full 11-section document can be exercised
    without a real network call. Core-gated and direct_input sections aren't
    mocked here -- they never reach an LLM call site at all in Step 2/3.
    target_audience's combined claims+personas call site is included so the
    resulting document can actually satisfy QualityCheckpoint.personas_grounded
    (competitor_count_ok is satisfied differently -- insufficient_evidence is
    exempt, not faked, since Core genuinely doesn't exist yet)."""
    from app.domain.claim import DerivedClaimDraft

    def _fake_synthesize(section: str, context, cost_tracker=None):
        chunk = context.chunks[0]
        return [ClaimDraft(section=section, text=f"Grounded claim for {section}.", chunk_id=chunk.chunk_id)]

    def _fake_synthesize_with_personas(section: str, context, cost_tracker=None):
        chunk = context.chunks[0]
        claims = [ClaimDraft(section=section, text=f"Grounded claim for {section}.", chunk_id=chunk.chunk_id)]
        personas = [
            AudiencePersonaDraft(
                section=section,
                name="Busy professional",
                pain_points=["No time to brew coffee well"],
                interests=["Convenience", "Quality"],
                chunk_ids=[chunk.chunk_id],
            )
        ]
        return claims, personas

    def _fake_synthesize_from_prior(section: str, upstream, missing_sections, cost_tracker=None):
        claim = upstream[0].claims[0]
        return [
            DerivedClaimDraft(section=section, text=f"Derived claim for {section}.", source_claim_ids=[claim.claim_id])
        ]

    monkeypatch.setattr("app.orchestration.llm.call_synthesize", _fake_synthesize)
    monkeypatch.setattr("app.orchestration.llm.call_synthesize_with_personas", _fake_synthesize_with_personas)
    monkeypatch.setattr("app.orchestration.llm.call_synthesize_from_prior", _fake_synthesize_from_prior)
