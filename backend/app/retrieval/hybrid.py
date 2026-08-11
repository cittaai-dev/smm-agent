from app.domain.chunk import Chunk
from app.domain.retrieval import RetrievalPlan
from app.retrieval.dense import search_dense
from app.retrieval.rerank import rerank
from app.retrieval.sparse import search_sparse


def _rrf_fuse(dense: list[Chunk], sparse: list[Chunk], k: int = 60) -> list[Chunk]:
    """Reciprocal Rank Fusion, not score fusion (pipeline.md §4.3): dense cosine
    and sparse ts_rank sit on different, untuned scales, and RRF needs no
    normalization to combine them. Score fusion was rejected because the
    weight becomes a tunable hyperparameter with no principled default --
    exactly the kind of knob this pipeline avoids."""
    scores: dict[str, float] = {}
    for rank, c in enumerate(dense):
        scores[c.chunk_id] = scores.get(c.chunk_id, 0.0) + 1.0 / (k + rank)
    for rank, c in enumerate(sparse):
        scores[c.chunk_id] = scores.get(c.chunk_id, 0.0) + 1.0 / (k + rank)
    by_id = {c.chunk_id: c for c in [*dense, *sparse]}
    return [by_id[cid] for cid, _ in sorted(scores.items(), key=lambda item: -item[1])]


def search_hybrid(kb_id: str, plan: RetrievalPlan) -> list[Chunk]:
    dense_results = search_dense(kb_id, plan)
    sparse_results = search_sparse(kb_id, plan)
    fused = _rrf_fuse(dense_results, sparse_results)[: plan.k_per_query]
    # Reranked against the first sub-query, matching the query the RetrievalPlan
    # was primarily built for -- fusion already merged all sub-queries' results,
    # reranking against all of them individually has no single well-defined
    # query to score against.
    return rerank(fused, plan.sub_queries[0]) if plan.sub_queries else fused
