"""step 3: sparse retrieval (tsvector + GIN), rerank cache, and the
annotate -> approve -> distribute workflow, keyed on market_research_document
(the real Step 2+ approval unit), not the legacy per-section deliverable.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-11
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Generated column: Postgres derives it from `text` on every insert/update,
    # so workers/ingest.py needs no changes and it can never drift out of sync
    # the way an app-maintained column could.
    op.execute(
        "ALTER TABLE chunk ADD COLUMN tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', text)) STORED"
    )
    op.execute("CREATE INDEX chunk_tsv_idx ON chunk USING GIN (tsv)")

    op.execute(
        """
        CREATE TABLE strategic_note (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES market_research_document(id),
            section TEXT NOT NULL,
            text TEXT NOT NULL,
            author TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX strategic_note_document_id_idx ON strategic_note (document_id)")

    op.execute(
        """
        CREATE TABLE approval_gate (
            document_id TEXT PRIMARY KEY REFERENCES market_research_document(id),
            approver_id TEXT,
            decision TEXT,
            note TEXT,
            checkpoint JSONB NOT NULL,
            decided_at TIMESTAMPTZ
        )
        """
    )

    op.execute(
        """
        CREATE TABLE distribution_record (
            document_id TEXT PRIMARY KEY REFERENCES market_research_document(id),
            internal BOOLEAN NOT NULL,
            client BOOLEAN NOT NULL,
            distributed_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )

    # Persistent, cross-process/cross-restart cache -- the in-process
    # lru_cache in retrieval/rerank.py only survives a single worker's
    # lifetime; this is the layer that actually avoids re-scoring an
    # identical (query, chunk_id) pair across separate runs or workers.
    op.execute(
        """
        CREATE TABLE rerank_cache (
            query_hash TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            score FLOAT NOT NULL,
            PRIMARY KEY (query_hash, chunk_id)
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rerank_cache")
    op.execute("DROP TABLE IF EXISTS distribution_record")
    op.execute("DROP TABLE IF EXISTS approval_gate")
    op.execute("DROP TABLE IF EXISTS strategic_note")
    op.execute("DROP INDEX IF EXISTS chunk_tsv_idx")
    op.execute("ALTER TABLE chunk DROP COLUMN IF EXISTS tsv")
