"""step 4 gate: brand ownership, api-key grants, real user identity.

Lands first, as its own PR, before Market Intel Core (step4_evidence_expansion.md
§0) -- additive only, no existing table touched, so Step 1-3's proven routes
and tests are unaffected until a follow-up PR wires resolve_brand_scope /
current_user into api/routes.py.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-11
"""
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE app_user (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE brand (
            id TEXT PRIMARY KEY,
            owner_org_id TEXT NOT NULL,
            created_by TEXT NOT NULL REFERENCES app_user(id),
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX brand_owner_org_idx ON brand (owner_org_id)")

    op.execute(
        """
        CREATE TABLE api_key (
            id TEXT PRIMARY KEY,
            owner_user_id TEXT NOT NULL REFERENCES app_user(id),
            key_hash TEXT UNIQUE NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now(),
            revoked_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE brand_grant (
            api_key_id TEXT NOT NULL REFERENCES api_key(id),
            brand_id TEXT NOT NULL REFERENCES brand(id),
            granted_at TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (api_key_id, brand_id)
        )
        """
    )
    op.execute("CREATE INDEX brand_grant_brand_idx ON brand_grant (brand_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS brand_grant")
    op.execute("DROP TABLE IF EXISTS api_key")
    op.execute("DROP TABLE IF EXISTS brand")
    op.execute("DROP TABLE IF EXISTS app_user")
