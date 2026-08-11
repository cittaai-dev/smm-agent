from app.domain.chunk import Block
from app.ingestion.router import route_and_chunk
from app.ingestion.validators import validate_batch

_KB = "run:test-brand"
_DOC = "doc-1"


def _blocks(*texts: str, structural: bool = True) -> list[Block]:
    return [
        Block(text=t, start=i, end=i, is_structural=structural, confidence=1.0)
        for i, t in enumerate(texts)
    ]


def test_l1_structural_block_is_not_degraded():
    [chunk] = route_and_chunk(_DOC, _KB, _blocks("Acme Store is a retailer."))
    assert not chunk.degraded
    assert chunk.order_confidence == 1.0


def test_non_structural_block_forced_to_l0_and_confidence_capped():
    [chunk] = route_and_chunk(_DOC, _KB, _blocks("garbled ocr text", structural=False))
    assert chunk.degraded
    assert chunk.order_confidence <= 0.5


def test_force_l0_degrades_every_chunk_regardless_of_structure():
    chunks = route_and_chunk(_DOC, _KB, _blocks("A heading", "Body text."), force_l0=True)
    assert all(c.degraded for c in chunks)
    assert all(c.order_confidence <= 0.5 for c in chunks)


def test_heading_carries_forward_to_following_content():
    blocks = _blocks("Company Overview", "Acme Store was founded in 2016 in Denver.")
    heading, content = route_and_chunk(_DOC, _KB, blocks)
    assert heading.heading_path == []  # the heading names itself, not "under" itself
    assert content.heading_path == ["Company Overview"]


def test_router_is_deterministic_across_calls():
    blocks = _blocks("Company Overview", "Acme Store was founded in 2016 in Denver.")
    first = route_and_chunk(_DOC, _KB, blocks)
    second = route_and_chunk(_DOC, _KB, blocks)
    assert [c.chunk_id for c in first] == [c.chunk_id for c in second]


def test_validate_batch_all_pass_on_clean_input():
    chunks = route_and_chunk(_DOC, _KB, _blocks("Company Overview", "Founded in 2016."))
    results = validate_batch(chunks)
    assert all(r.passed for r in results)


def test_c1_atomicity_fails_on_empty_chunk():
    blocks = _blocks("")
    chunks = route_and_chunk(_DOC, _KB, blocks)
    results = {r.code: r for r in validate_batch(chunks)}
    assert not results["C1"].passed


def test_c4_fails_if_degraded_chunk_claims_high_confidence():
    # simulate a router bug: L0 chunk that didn't get its confidence capped
    from app.domain.chunk import Chunk

    bad_chunk = Chunk(
        chunk_id="x", kb_id=_KB, doc_id=_DOC, block_span=(0, 0),
        text="text", order_confidence=0.9, degraded=True,
    )
    results = {r.code: r for r in validate_batch([bad_chunk])}
    assert not results["C4"].passed
