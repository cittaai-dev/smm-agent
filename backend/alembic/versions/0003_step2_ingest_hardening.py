"""step 2: multi-file source tracking, team-provided input, chunk heading path,
market_research_document assembly.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-11
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE chunk ADD COLUMN heading_path TEXT[]")
    op.execute("ALTER TABLE document_registry ADD COLUMN source_kind TEXT")

    op.execute(
        """
        CREATE TABLE source_file (
            file_id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            mime_type TEXT,
            size_bytes INT,
            source_kind TEXT NOT NULL,
            status TEXT NOT NULL,
            degraded_reason TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX source_file_brand_id_idx ON source_file (brand_id)")

    op.execute(
        """
        CREATE TABLE team_input (
            brand_id TEXT NOT NULL,
            section TEXT NOT NULL,
            text TEXT NOT NULL,
            author TEXT,
            updated_at TIMESTAMPTZ DEFAULT now(),
            PRIMARY KEY (brand_id, section)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE market_research_document (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL,
            sections JSONB NOT NULL,
            status TEXT NOT NULL,
            call_site_trace JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS market_research_document")
    op.execute("DROP TABLE IF EXISTS team_input")
    op.execute("DROP TABLE IF EXISTS source_file")
    op.execute("ALTER TABLE document_registry DROP COLUMN IF EXISTS source_kind")
    op.execute("ALTER TABLE chunk DROP COLUMN IF EXISTS heading_path")
