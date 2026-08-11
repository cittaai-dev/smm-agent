"""foundation: document_registry, chunk, deliverable

Revision ID: 0001
Revises:
Create Date: 2026-08-11
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute(
        """
        CREATE TABLE document_registry (
            doc_id TEXT PRIMARY KEY,
            kb_id TEXT NOT NULL,
            content_hash TEXT UNIQUE NOT NULL,
            source_uri TEXT,
            ingested_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    op.execute(
        """
        CREATE TABLE chunk (
            chunk_id TEXT PRIMARY KEY,
            kb_id TEXT NOT NULL,
            doc_id TEXT REFERENCES document_registry(doc_id),
            block_span INT4RANGE,
            text TEXT NOT NULL,
            embedding VECTOR(1536),
            order_confidence FLOAT DEFAULT 1.0,
            degraded BOOLEAN DEFAULT FALSE
        )
        """
    )
    op.execute("CREATE INDEX chunk_kb_id_idx ON chunk (kb_id)")
    op.execute(
        "CREATE INDEX chunk_embedding_idx ON chunk USING ivfflat (embedding vector_cosine_ops)"
    )

    op.execute(
        """
        CREATE TABLE deliverable (
            id TEXT PRIMARY KEY,
            brand_id TEXT NOT NULL,
            status TEXT NOT NULL,
            claims JSONB NOT NULL,
            call_site_trace JSONB NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS deliverable")
    op.execute("DROP TABLE IF EXISTS chunk")
    op.execute("DROP TABLE IF EXISTS document_registry")
