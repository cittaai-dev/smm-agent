from datetime import datetime

from pydantic import BaseModel


class Brand(BaseModel):
    """Owns a `run:<brand_id>` KB. Closes the gap named in step4_evidence_expansion.md
    §0: brand_id was free text typed into a form, unauthenticated, unowned --
    everything Step 4 adds (shared Core corpus, cross-brand BRIDGE matching)
    makes that gap more expensive to leave open."""

    id: str
    owner_org_id: str
    created_by: str  # User.id
    created_at: datetime


class BrandGrant(BaseModel):
    """One row = one api_key_id may act on one brand_id. The minimal app-layer
    check that stands in for Step 5's full Postgres RLS -- deliberately not
    that yet (dev_guidelines.md: don't build the general case before the
    concrete need forces it)."""

    api_key_id: str
    brand_id: str
    granted_at: datetime
