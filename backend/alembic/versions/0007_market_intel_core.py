"""step 4: Market Intel Core -- kb_version, promotion workflow, golden set,
chunk.strategy for the L0-L3 ladder.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-11
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunk ADD COLUMN strategy TEXT NOT NULL DEFAULT 'L1'")

    op.execute(
        """
        CREATE TABLE kb_version (
            kb_id TEXT PRIMARY KEY,
            version INT NOT NULL,
            status TEXT NOT NULL,
            eval_gate_result JSONB,
            promoted_at TIMESTAMPTZ,
            promoted_by TEXT REFERENCES app_user(id)
        )
        """
    )
    op.execute("CREATE INDEX kb_version_status_idx ON kb_version (status)")

    op.execute(
        """
        CREATE TABLE promotion_request (
            id TEXT PRIMARY KEY,
            -- ON UPDATE CASCADE: decide_promotion() renames kb_version.kb_id
            -- from the staging id to the promoted id in the same transaction
            -- as promoting it; this keeps the FK intact without a second
            -- explicit UPDATE on this table.
            kb_id TEXT NOT NULL REFERENCES kb_version(kb_id) ON UPDATE CASCADE,
            source_summary TEXT NOT NULL,
            requested_by TEXT NOT NULL REFERENCES app_user(id),
            status TEXT NOT NULL DEFAULT 'pending',
            reviewed_by TEXT REFERENCES app_user(id),
            reviewed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX promotion_request_status_idx ON promotion_request (status)")

    op.execute(
        """
        CREATE TABLE golden_case (
            id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            section TEXT NOT NULL,
            fixture_chunks JSONB NOT NULL DEFAULT '[]'
        )
        """
    )

    op.execute(
        """
        CREATE TABLE core_competitor_registry (
            competitor_id TEXT PRIMARY KEY,
            industry_tag TEXT NOT NULL,
            name TEXT NOT NULL,
            homepage_url TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX core_competitor_industry_idx ON core_competitor_registry (industry_tag)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS core_competitor_registry")
    op.execute("DROP TABLE IF EXISTS golden_case")
    op.execute("DROP TABLE IF EXISTS promotion_request")
    op.execute("DROP TABLE IF EXISTS kb_version")
    op.execute("ALTER TABLE chunk DROP COLUMN IF EXISTS strategy")
