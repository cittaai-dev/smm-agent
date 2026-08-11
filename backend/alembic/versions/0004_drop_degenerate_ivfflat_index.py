"""fix: chunk_embedding_idx (ivfflat) was created in 0001 on an empty table, so
its cluster centroids were trained on zero rows. At Brand Workspace scale (a
handful to low hundreds of chunks per kb_id), this produces silently wrong
nearest-neighbor results -- reproduced deterministically with as few as 2 rows
in a kb_id partition, where the "top k by cosine distance" query would
sometimes return zero rows for a query embedding that should have matched.

Exact (index-free) cosine search is both correct and fast enough at this
scale. A real ANN index (ivfflat with a properly sized `lists`, or hnsw)
belongs at Market Intel Core scale (Step 4+), built with an ANALYZE/REINDEX
discipline that accounts for training-data volume -- not reintroduced here
speculatively.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-11
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS chunk_embedding_idx")


def downgrade() -> None:
    op.execute("CREATE INDEX chunk_embedding_idx ON chunk USING ivfflat (embedding vector_cosine_ops)")
