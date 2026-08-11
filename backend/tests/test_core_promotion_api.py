import hashlib

from fastapi.testclient import TestClient

from app.infra.db import get_session
from app.infra.embeddings import embed, embedding_to_sql
from app.main import app

client = TestClient(app)


def _seed_user(user_id: str, api_key: str) -> None:
    key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    with get_session() as session:
        session.execute(
            "INSERT INTO app_user (id, email, role) VALUES (:id, :email, 'team_lead')",
            {"id": user_id, "email": f"{user_id}@example.com"},
        )
        session.execute(
            "INSERT INTO api_key (id, owner_user_id, key_hash) VALUES (:id, :user, :hash)",
            {"id": f"key-{api_key}", "user": user_id, "hash": key_hash},
        )
        session.commit()


def _stage_version(version: int) -> str:
    kb_id = f"core:market-intel@v{version}:staging"
    with get_session() as session:
        session.execute(
            "INSERT INTO kb_version (kb_id, version, status) VALUES (:kb, :v, 'staging')",
            {"kb": kb_id, "v": version},
        )
        session.execute(
            "INSERT INTO document_registry (doc_id, kb_id, content_hash, source_uri) "
            "VALUES ('doc-1', :kb, 'hash-1', 'test')",
            {"kb": kb_id},
        )
        text = "Fitness category engagement benchmark data point."
        session.execute(
            """INSERT INTO chunk (chunk_id, kb_id, doc_id, block_span, text, embedding, order_confidence)
               VALUES ('c1', :kb, 'doc-1', int4range(0, 1, '[]'), :text, (:emb)::vector, 1.0)""",
            {"kb": kb_id, "text": text, "emb": embedding_to_sql(embed(text))},
        )
        session.commit()
    return kb_id


def test_promotion_requires_authenticated_user():
    resp = client.post("/core/staging/1/promotion-requests", json={"source_summary": "x"})
    assert resp.status_code in (401, 422)  # missing api-key header


def test_promotion_request_evaluates_and_blocks_missing_staging():
    _seed_user("u1", "key-1")
    resp = client.post(
        "/core/staging/999/promotion-requests",
        json={"source_summary": "no such staging build"},
        headers={"api-key": "key-1"},
    )
    assert resp.status_code == 404


def test_full_promotion_flow_approve(monkeypatch):
    _seed_user("u2", "key-2")
    _stage_version(1)

    from app.domain.claim import VerifiedClaim

    monkeypatch.setattr(
        "app.eval.golden_runner.default_synthesis_runner",
        lambda case, kb: [VerifiedClaim(claim_id="cl1", section="market_overview", text="x", chunk_id="c1", verified=True)],
    )

    resp = client.post(
        "/core/staging/1/promotion-requests",
        json={"source_summary": "curated market research"},
        headers={"api-key": "key-2"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["eval_result"]["passed"]
    request_id = body["request_id"]

    decide_resp = client.post(
        f"/core/promotion-requests/{request_id}/decide",
        json={"decision": "approved"},
        headers={"api-key": "key-2"},
    )
    assert decide_resp.status_code == 200, decide_resp.text
    assert decide_resp.json()["kb_id"] == "core:market-intel@v1"

    with get_session() as session:
        promoted_count = session.execute(
            "SELECT count(*) FROM chunk WHERE kb_id = 'core:market-intel@v1'"
        ).scalar()
        staging_count = session.execute(
            "SELECT count(*) FROM chunk WHERE kb_id = 'core:market-intel@v1:staging'"
        ).scalar()
    assert promoted_count == 1
    assert staging_count == 0

    versions_resp = client.get("/core/versions")
    assert any(v["kb_id"] == "core:market-intel@v1" and v["status"] == "promoted" for v in versions_resp.json())
