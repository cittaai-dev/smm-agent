from typing import Literal

from pydantic import BaseModel


class ClaimDraft(BaseModel):
    section: Literal["brand_overview"]  # only §1 in Step 1
    text: str
    chunk_id: str | None = None


class VerifiedClaim(BaseModel):
    section: str
    text: str
    chunk_id: str
    block_span: tuple[int, int]
    verified: bool
    rejection_reason: Literal["missing_chunk", "no_citation"] | None = None
