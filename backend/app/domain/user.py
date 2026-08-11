from typing import Literal

from pydantic import BaseModel


class User(BaseModel):
    """Real identity behind approval_gate/strategic_note authorship. Step 1-3's
    approver_id/author fields were free text in the request body -- this is the
    type that replaces "whatever string the client sent" with a resolved,
    looked-up identity (api/deps.py's current_user)."""

    id: str
    email: str
    role: Literal["team_lead", "smm", "graphic_designer", "admin"]
