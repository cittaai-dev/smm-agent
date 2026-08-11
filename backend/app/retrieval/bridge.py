from pydantic import BaseModel

from app.domain.chunk import Chunk
from app.domain.retrieval import RetrievalPlan
from app.infra.settings import bridge_settings
from app.retrieval.dense import search_dense


class BridgePair(BaseModel):
    """One run chunk + one core chunk that satisfy a section's bridge
    relation. §6 (competitor_analysis): for each run chunk describing a
    brand-observed competitor signal, find the core chunk that benchmarks the
    same metric for the same/comparable competitor. §9 (platform_analysis):
    for each run chunk reporting the brand's own platform performance, find
    the core chunk stating category-norm cadence/engagement for that
    platform."""

    run_chunk: Chunk
    core_chunk: Chunk


def search_bridge(brand_kb_id: str, core_kb_id: str, plan: RetrievalPlan) -> list[BridgePair]:
    """Fanout is bounded, not hoped-for (dual-kb.md §10): bridge_settings caps
    both the run-chunk fanout and the total pair count, so cost is a fixed,
    instrumented budget rather than an open-ended search. Each run chunk's
    own text becomes the query into Core -- the run chunk *is* the bridge
    relation's left-hand side.
    """
    run_chunks = search_dense(brand_kb_id, plan)[: bridge_settings.max_run_chunks]

    pairs: list[BridgePair] = []
    for run_chunk in run_chunks:
        if len(pairs) >= bridge_settings.max_total_pairs:
            break
        core_plan = RetrievalPlan(
            sub_queries=[run_chunk.text], k_per_query=bridge_settings.max_core_matches_per_chunk
        )
        for core_chunk in search_dense(core_kb_id, core_plan):
            if len(pairs) >= bridge_settings.max_total_pairs:
                break
            pairs.append(BridgePair(run_chunk=run_chunk, core_chunk=core_chunk))

    return pairs
