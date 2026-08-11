from app.domain.claim import VerifiedClaim
from app.domain.kb_version import GoldenCase
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.verify import verify_claims
from app.retrieval.dense import search_dense


def default_synthesis_runner(case: GoldenCase, staging_kb_id: str) -> list[VerifiedClaim]:
    """The real (non-test-double) SynthesisRunner for app/eval/gate.py, used by
    the /promotion-requests endpoint. Ingest-time-exempt (P2): a golden case's
    topic is its fixed query, so this replays only the synthesize call site,
    never plan -- a golden case's whole point is a stable, reproducible probe,
    not a model deciding what to search for."""
    from app.orchestration.llm import call_synthesize

    plan = RetrievalPlan(sub_queries=[case.topic], k_per_query=8)
    context = RetrievedContext(chunks=search_dense(staging_kb_id, plan), plan=plan)
    if not context.chunks:
        return []
    claims = call_synthesize(section=case.section, context=context)
    return verify_claims(claims, context)
