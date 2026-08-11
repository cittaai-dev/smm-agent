import hashlib
from typing import Literal

from app.domain.chunk import Block, Chunk, ChunkStrategy
from app.infra.settings import core_ingest_settings

# A degraded (L0) chunk never gets to claim structural-parse confidence -- this
# cap is what C4 (monotonic escalation) checks: strategy and confidence must
# never disagree about how much to trust a chunk.
L0_CONFIDENCE_CEILING = 0.5

# ladder -> strategy ceiling. Brand Workspace stays L0/L1 (Step 2's proven
# profile); Core's L0-L3 is what Step 4's core_builder.py opts into -- same
# function, same validators, only this ceiling differs (dual-kb.md: "same
# code, different config").
_LADDER_CEILING: dict[str, int] = {"L0-L1": 1, "L0-L3": 3}


def _looks_like_heading(text: str) -> bool:
    line = text.strip()
    if not line or len(line) > 80:
        return False
    if line.endswith((".", "?", "!", ":")):
        return False
    return len(line.split()) <= 12


def _select_strategy(block: Block, is_l1: bool, ceiling: int) -> ChunkStrategy:
    if not is_l1:
        return "L0"
    if ceiling <= 1:
        return "L1"
    # Core-only ladder: escalate by text length, a coarse but deterministic
    # proxy for "how much standalone context this block already carries"
    # until real section-aggregation exists. Never escalates past `ceiling`,
    # and a short structural block still correctly stays L1.
    length = len(block.text)
    if ceiling >= 3 and length >= core_ingest_settings.l3_min_chars:
        return "L3"
    if ceiling >= 2 and length >= core_ingest_settings.l2_min_chars:
        return "L2"
    return "L1"


def route_and_chunk(
    doc_id: str,
    kb_id: str,
    blocks: list[Block],
    force_l0: bool = False,
    ladder: Literal["L0-L1", "L0-L3"] = "L0-L1",
) -> list[Chunk]:
    """Brand Workspace profile (ladder="L0-L1", the default every Step 2
    caller already uses): L1 structural default, L0 floor. Market Intel Core
    (ladder="L0-L3", Step 4's core_builder.py) raises the ceiling to L3 --
    same routing pass, same C1-C8 validators, only `ceiling` changes.

    heading_path is a lightweight carry-forward heuristic (short, unpunctuated
    line -> treated as a heading for whatever follows it), not real document
    structure parsing -- good enough to let a reviewer navigate a citation back
    toward its section without pretending to be a layout engine.
    """
    ceiling = _LADDER_CEILING[ladder]
    chunks: list[Chunk] = []
    heading_stack: list[str] = []
    for block in blocks:
        is_l1 = block.is_structural and not force_l0
        is_heading = is_l1 and _looks_like_heading(block.text)
        if is_heading:
            heading_stack = [block.text.strip()]

        strategy = _select_strategy(block, is_l1, ceiling)
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
                strategy=strategy,
            )
        )
    return chunks
