from pydantic import BaseModel


class Chunk(BaseModel):
    chunk_id: str
    kb_id: str  # "run:<brand_id>" only in Step 1
    doc_id: str
    block_span: tuple[int, int]
    text: str
    order_confidence: float = 1.0
    degraded: bool = False
