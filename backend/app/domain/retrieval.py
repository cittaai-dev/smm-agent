from typing import Literal

from pydantic import BaseModel

from app.domain.chunk import Chunk


class RetrievalPlan(BaseModel):
    sub_queries: list[str]
    filters: dict[str, str] = {}
    topology: Literal["union"] = "union"  # BRIDGE not available until Step 5
    k_per_query: int = 8


class RetrievedContext(BaseModel):
    chunks: list[Chunk]
    plan: RetrievalPlan
