from app.domain.chunk import Chunk
from app.domain.claim import ClaimDraft
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.verify import verify_claims

_PLAN = RetrievalPlan(sub_queries=["q"])
_CHUNK = Chunk(chunk_id="c1", kb_id="run:b", doc_id="d1", block_span=(0, 0), text="evidence")
_CONTEXT = RetrievedContext(chunks=[_CHUNK], plan=_PLAN)


def test_verified_claim_resolves_block_span():
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id="c1")]
    [result] = verify_claims(claims, _CONTEXT)
    assert result.verified
    assert result.block_span == _CHUNK.block_span
    assert result.rejection_reason is None


def test_missing_chunk_id_rejected_as_no_citation():
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id=None)]
    [result] = verify_claims(claims, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "no_citation"


def test_fabricated_chunk_id_rejected_as_missing_chunk():
    claims = [ClaimDraft(section="brand_overview", text="claim", chunk_id="does-not-exist")]
    [result] = verify_claims(claims, _CONTEXT)
    assert not result.verified
    assert result.rejection_reason == "missing_chunk"
