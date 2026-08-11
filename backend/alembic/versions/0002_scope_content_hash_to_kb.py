"""fix: content_hash dedup was global, silently no-oping ingest for a second
brand that happened to upload a file with a hash already seen under another
brand's kb_id.

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-11
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE document_registry DROP CONSTRAINT document_registry_content_hash_key")
    op.execute(
        "ALTER TABLE document_registry ADD CONSTRAINT document_registry_kb_content_uq "
        "UNIQUE (kb_id, content_hash)"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE document_registry DROP CONSTRAINT document_registry_kb_content_uq")
    op.execute(
        "ALTER TABLE document_registry ADD CONSTRAINT document_registry_content_hash_key "
        "UNIQUE (content_hash)"
    )
