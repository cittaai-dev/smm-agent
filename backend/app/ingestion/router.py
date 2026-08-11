import hashlib

from app.domain.chunk import Block, Chunk

# A degraded (L0) chunk never gets to claim structural-parse confidence -- this
# cap is what C4 (monotonic escalation) checks: strategy and confidence must
# never disagree about how much to trust a chunk.
L0_CONFIDENCE_CEILING = 0.5


def _looks_like_heading(text: str) -> bool:
    line = text.strip()
    if not line or len(line) > 80:
        return False
    if line.endswith((".", "?", "!", ":")):
        return False
    return len(line.split()) <= 12


def route_and_chunk(
    doc_id: str, kb_id: str, blocks: list[Block], force_l0: bool = False
) -> list[Chunk]:
    """Brand Workspace profile: L1 structural default, L0 floor. No L2/L3 --
    those are Core-only ladders (dual-kb.md), out of scope until Step 4.

    heading_path is a lightweight carry-forward heuristic (short, unpunctuated
    line -> treated as a heading for whatever follows it), not real document
    structure parsing -- good enough to let a reviewer navigate a citation back
    toward its section without pretending to be a layout engine.
    """
    chunks: list[Chunk] = []
    heading_stack: list[str] = []
    for block in blocks:
        is_l1 = block.is_structural and not force_l0
        is_heading = is_l1 and _looks_like_heading(block.text)
        if is_heading:
            heading_stack = [block.text.strip()]

        span = (block.start, block.end)
        chunk_id = hashlib.sha256(f"{doc_id}:{span}:{kb_id}:v1".encode()).hexdigest()
        confidence = block.confidence if is_l1 else min(block.confidence, L0_CONFIDENCE_CEILING)
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                kb_id=kb_id,
                doc_id=doc_id,
                block_span=span,
                text=block.text,
                order_confidence=confidence,
                degraded=not is_l1,
                heading_path=[] if (is_heading or not is_l1) else list(heading_stack),
            )
        )
    return chunks
