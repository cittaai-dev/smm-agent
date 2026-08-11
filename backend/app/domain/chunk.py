from pydantic import BaseModel


class Block(BaseModel):
    """Parser output, pre-chunking. P1: Block IR crosses parse->chunk, never
    further -- route_and_chunk() is the only thing that reads this type."""

    text: str
    start: int
    end: int
    is_structural: bool = True  # False forces L0 (e.g. no reliable paragraph boundary)
    confidence: float = 1.0


class Chunk(BaseModel):
    chunk_id: str
    kb_id: str  # "run:<brand_id>" for Brand Workspace
    doc_id: str
    block_span: tuple[int, int]
    text: str
    order_confidence: float = 1.0
    degraded: bool = False
    heading_path: list[str] = []
