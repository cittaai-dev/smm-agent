import pytest

from app.domain.chunk import Chunk
from app.domain.retrieval import RetrievalPlan
from app.retrieval.dense import search_dense
from app.retrieval.hybrid import _rrf_fuse, search_hybrid
from app.retrieval.sparse import search_sparse
from app.workers.ingest import ingest_file

_KB = "run:hybrid-test"


def _chunk(cid: str) -> Chunk:
    return Chunk(chunk_id=cid, kb_id=_KB, doc_id="d1", block_span=(0, 0), text="x")


def test_rrf_fuse_ranks_a_chunk_present_in_both_lists_above_either_alone():
    shared = _chunk("shared")
    dense_only = _chunk("dense-only")
    sparse_only = _chunk("sparse-only")
    dense = [shared, dense_only]
    sparse = [sparse_only, shared]

    fused = _rrf_fuse(dense, sparse)

    assert fused[0].chunk_id == "shared"
    assert {c.chunk_id for c in fused} == {"shared", "dense-only", "sparse-only"}


def test_rrf_fuse_is_deterministic():
    dense = [_chunk("a"), _chunk("b")]
    sparse = [_chunk("b"), _chunk("c")]
    assert [c.chunk_id for c in _rrf_fuse(dense, sparse)] == [
        c.chunk_id for c in _rrf_fuse(dense, sparse)
    ]


def test_search_hybrid_rejects_unscoped_kb_id():
    # P3 fail-fast: a caller that doesn't pass a run:/core: scoped kb_id
    # should error loudly here, not silently fall through to RLS alone.
    plan = RetrievalPlan(sub_queries=["q"], k_per_query=5)
    with pytest.raises(ValueError, match="not a recognized run:/core: scope"):
        search_hybrid(kb_id="hybrid-test", plan=plan)


def test_search_hybrid_unions_dense_and_sparse_results(tmp_path):
    # A keyword-distinctive term ("Glacierweave") sparse search should rank
    # highly via ts_rank regardless of how embeddings happen to place it --
    # proves search_hybrid actually surfaces sparse-side matches, not just
    # whatever search_dense alone would already return.
    path = tmp_path / "brand.txt"
    path.write_text(
        "Acme Store's proprietary fabric is called Glacierweave, a three-layer "
        "waterproof-breathable textile used in all winter product lines.\n\n"
        "The company also sells cookware, backpacks, and camp furniture for "
        "weekend car campers."
    )
    ingest_file(brand_id="hybrid-test", file_path=str(path))

    plan = RetrievalPlan(sub_queries=["Glacierweave fabric"], k_per_query=5)
    hybrid_results = search_hybrid(kb_id=_KB, plan=plan)
    sparse_results = search_sparse(kb_id=_KB, plan=plan)

    assert sparse_results, "sparse search should find the exact keyword match"
    sparse_ids = {c.chunk_id for c in sparse_results}
    hybrid_ids = {c.chunk_id for c in hybrid_results}
    assert sparse_ids & hybrid_ids, "hybrid must include what sparse alone found"


def test_search_hybrid_degrades_gracefully_to_dense_floor_when_no_keyword_match(tmp_path):
    # A purely semantic query with no literal keyword overlap: sparse finds
    # nothing, hybrid must still return dense's results, not an empty set --
    # P5's floor still holds once hybrid is the default path.
    path = tmp_path / "brand.txt"
    path.write_text("Acme Store ships tents and sleeping bags to campers nationwide.")
    ingest_file(brand_id="hybrid-test", file_path=str(path))

    plan = RetrievalPlan(sub_queries=["outdoor gear retailer"], k_per_query=5)
    dense_results = search_dense(kb_id=_KB, plan=plan)
    hybrid_results = search_hybrid(kb_id=_KB, plan=plan)

    assert dense_results
    assert {c.chunk_id for c in dense_results} <= {c.chunk_id for c in hybrid_results}
