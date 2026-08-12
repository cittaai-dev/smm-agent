import hashlib

from fastapi import Header, HTTPException, Path

from app.domain.user import User
from app.infra.db import get_session
from app.infra.settings import auth_settings


def _hash_key(api_key: str) -> str:
    # Same content-addressed discipline as chunk_id/doc_id elsewhere in this
    # codebase -- store the hash, never the plaintext key.
    return hashlib.sha256(api_key.encode()).hexdigest()


def _lookup_api_key(api_key: str) -> tuple[str, str] | None:
    """Returns (api_key_id, owner_user_id) or None if the key is unknown/revoked."""
    with get_session() as session:
        row = session.execute(
            "SELECT id, owner_user_id FROM api_key WHERE key_hash = :h AND revoked_at IS NULL",
            {"h": _hash_key(api_key)},
        ).mappings().first()
    return (row["id"], row["owner_user_id"]) if row else None


async def resolve_brand_scope(brand_id: str = Path(...), api_key: str = Header(...)) -> str:
    """Every brand-scoped route depends on this. Confinement before retrieval
    (P3): the grant is checked here, at the API boundary, never as a post-hoc
    filter on results already fetched for the wrong brand."""
    if auth_settings.dev_bypass:
        return f"run:{brand_id}"

    resolved = _lookup_api_key(api_key)
    if resolved is None:
        raise HTTPException(403, detail="invalid or revoked api key")
    api_key_id, _owner_user_id = resolved

    with get_session() as session:
        grant = session.execute(
            "SELECT 1 FROM brand_grant WHERE api_key_id = :k AND brand_id = :b",
            {"k": api_key_id, "b": brand_id},
        ).first()
    if grant is None:
        raise HTTPException(403, detail=f"not authorized for brand {brand_id}")
    return f"run:{brand_id}"


async def current_user(api_key: str = Header(...)) -> User:
    """Resolves the real identity behind an api_key -- what approval_gate /
    strategic_note authorship reads instead of a client-supplied string.
    Reuses the same api-key header resolve_brand_scope already validates;
    Step 5 is where a full session/JWT layer would replace this, not before."""
    if auth_settings.dev_bypass:
        return User(id=auth_settings.dev_user_id, email="dev@local", role="team_lead")

    resolved = _lookup_api_key(api_key)
    if resolved is None:
        raise HTTPException(401, detail="invalid or revoked api key")
    _api_key_id, owner_user_id = resolved

    with get_session() as session:
        row = session.execute(
            "SELECT id, email, role FROM app_user WHERE id = :id",
            {"id": owner_user_id},
        ).mappings().first()
    if row is None:
        raise HTTPException(401, detail="user not found")
    return User(**row)
