"""step 5: multi-tenant RLS (defense-in-depth), decision integrity (append-only
approval/distribution events), client distribution links, live data ingestion
trust boundary (per-brand encrypted credentials, market segment whitelist,
collection job log), chunk freshness fields.

Additive only -- old approval_gate/distribution_record tables are left in
place, read-only, per step5_trust_boundary.md Part C's migration note; a
follow-up release drops them once every read path is repointed.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-11
"""
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Part A: RLS (defense-in-depth on top of Step 4 §0's app-layer check) ---
    # NOLOGIN role, not a second Postgres login/password: infra/db.py's
    # kb-scoped session does `SET LOCAL ROLE brand_workspace_role` on the
    # app's existing connection rather than standing up a second credential.
    # SET ROLE (unlike SET SESSION AUTHORIZATION) fully drops the connecting
    # role's superuser/table-owner bypass for the rest of the transaction, so
    # this is sufficient for RLS to actually apply, not merely declarative.
    op.execute("CREATE ROLE brand_workspace_role NOLOGIN")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON chunk, document_registry, source_file TO brand_workspace_role")
    op.execute("GRANT brand_workspace_role TO current_user")

    op.execute("ALTER TABLE chunk ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY chunk_kb_isolation ON chunk
          USING (kb_id = current_setting('app.current_kb_id', true) OR kb_id LIKE 'core:%')
        """
    )

    op.execute("ALTER TABLE document_registry ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY doc_registry_kb_isolation ON document_registry
          USING (kb_id = current_setting('app.current_kb_id', true) OR kb_id LIKE 'core:%')
        """
    )

    op.execute("ALTER TABLE source_file ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY source_file_kb_isolation ON source_file
          USING (('run:' || brand_id) = current_setting('app.current_kb_id', true))
        """
    )

    # TTL sweep target -- Brand Workspace uploads are TTL-scoped per dual-kb.md;
    # Core builder never writes source_file rows, so no `core:` exemption needed here.
    op.execute("ALTER TABLE source_file ADD COLUMN ttl_expires_at TIMESTAMPTZ DEFAULT (now() + interval '90 days')")

    # --- Part C: decision integrity, append-only ---
    op.execute(
        """
        CREATE TABLE approval_event (
            id SERIAL PRIMARY KEY,
            document_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            approver_id TEXT NOT NULL,
            note TEXT,
            checkpoint JSONB,
            decided_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX approval_event_document_idx ON approval_event (document_id, decided_at)")

    op.execute(
        """
        CREATE TABLE distribution_event (
            id SERIAL PRIMARY KEY,
            document_id TEXT NOT NULL,
            channel TEXT NOT NULL,
            distributed_by TEXT NOT NULL,
            distributed_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX distribution_event_document_idx ON distribution_event (document_id, distributed_at)")

    # --- Part B: client distribution ---
    op.execute(
        """
        CREATE TABLE distribution_link (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            created_by TEXT NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ DEFAULT now()
        )
        """
    )
    op.execute("CREATE INDEX distribution_link_document_idx ON distribution_link (document_id)")

    # --- Part D: live data ingestion trust boundary ---
    op.execute(
        """
        CREATE TABLE data_source_credential (
            brand_id TEXT NOT NULL,
            source TEXT NOT NULL,
            encrypted_api_key TEXT NOT NULL,
            rate_limit_per_hour INT NOT NULL DEFAULT 60,
            created_at TIMESTAMPTZ DEFAULT now(),
            last_used_at TIMESTAMPTZ,
            PRIMARY KEY (brand_id, source)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE market_segment (
            brand_id TEXT PRIMARY KEY,
            segment_name TEXT NOT NULL,
            youtube_channel_keywords TEXT[] NOT NULL DEFAULT '{}',
            news_sources TEXT[] NOT NULL DEFAULT '{}',
            reddit_communities TEXT[] NOT NULL DEFAULT '{}',
            website_urls TEXT[] NOT NULL DEFAULT '{}',
            max_competitors_to_track INT NOT NULL DEFAULT 10
        )
        """
    )

    # Append-only, same discipline as approval_event/distribution_event above --
    # a collection run's history (including partial-source failures) is part
    # of the brand's record, not a status column that overwrites the last run.
    op.execute(
        """
        CREATE TABLE collection_job_status (
            id SERIAL PRIMARY KEY,
            brand_id TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT NOT NULL,
            reason TEXT,
            item_count INT NOT NULL DEFAULT 0,
            started_at TIMESTAMPTZ DEFAULT now(),
            finished_at TIMESTAMPTZ
        )
        """
    )
    op.execute("CREATE INDEX collection_job_status_brand_idx ON collection_job_status (brand_id, started_at)")

    # Chunk freshness -- Part D §6. Nullable: Brand Workspace uploads and Core
    # builder's curated documents have no meaningful staleness window; only
    # live-collected chunks set these.
    op.execute("ALTER TABLE chunk ADD COLUMN collected_at TIMESTAMPTZ")
    op.execute("ALTER TABLE chunk ADD COLUMN valid_until TIMESTAMPTZ")
    op.execute("ALTER TABLE chunk ADD COLUMN data_source TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE chunk DROP COLUMN IF EXISTS data_source")
    op.execute("ALTER TABLE chunk DROP COLUMN IF EXISTS valid_until")
    op.execute("ALTER TABLE chunk DROP COLUMN IF EXISTS collected_at")
    op.execute("DROP TABLE IF EXISTS collection_job_status")
    op.execute("DROP TABLE IF EXISTS market_segment")
    op.execute("DROP TABLE IF EXISTS data_source_credential")
    op.execute("DROP TABLE IF EXISTS distribution_link")
    op.execute("DROP TABLE IF EXISTS distribution_event")
    op.execute("DROP TABLE IF EXISTS approval_event")
    op.execute("ALTER TABLE source_file DROP COLUMN IF EXISTS ttl_expires_at")
    op.execute("DROP POLICY IF EXISTS source_file_kb_isolation ON source_file")
    op.execute("ALTER TABLE source_file DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS doc_registry_kb_isolation ON document_registry")
    op.execute("ALTER TABLE document_registry DISABLE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS chunk_kb_isolation ON chunk")
    op.execute("ALTER TABLE chunk DISABLE ROW LEVEL SECURITY")
    op.execute("REVOKE brand_workspace_role FROM current_user")
    op.execute("REVOKE ALL ON chunk, document_registry, source_file FROM brand_workspace_role")
    op.execute("DROP ROLE IF EXISTS brand_workspace_role")
