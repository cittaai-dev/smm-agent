from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DataSourceKind = Literal["google_trends", "newsapi", "youtube", "scrapy_competitor"]


class DataSourceCredential(BaseModel):
    """Per-brand, encrypted at rest -- a leaked key exposes only one brand's
    data collection, never every brand's (step5_trust_boundary.md Part D
    §4). api_key is plaintext only in transit (the API request/response
    shape); infra/crypto.py encrypts it before this ever reaches storage."""

    brand_id: str
    source: DataSourceKind
    api_key: str
    rate_limit_per_hour: int = 60
    created_at: datetime | None = None
    last_used_at: datetime | None = None
