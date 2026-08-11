from datetime import datetime
from typing import Literal

from pydantic import BaseModel

SourceKind = Literal["brand_material", "analytics", "competitor_upload"]
SourceFileStatus = Literal["uploading", "ingested", "degraded"]


class SourceFile(BaseModel):
    file_id: str
    brand_id: str
    filename: str
    source_kind: SourceKind
    status: SourceFileStatus
    degraded_reason: str | None = None
    created_at: datetime
