from fastapi.testclient import TestClient

from app.domain.chunk import Chunk
from app.domain.claim import ClaimDraft
from app.domain.retrieval import RetrievalPlan, RetrievedContext
from app.domain.verify import verify_claims
from app.main import app


def test_metrics_endpoint_is_exposed():
    client = TestClient(app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "smm_claims_total" in response.text


def test_claim_verification_updates_rejection_metric():
    client = TestClient(app)
    chunk = Chunk(chunk_id="c1", kb_id="run:x", doc_id="d1", block_span=(0, 0), text="evidence")
    context = RetrievedContext(chunks=[chunk], plan=RetrievalPlan(sub_queries=["q"]))

    verify_claims(
        [ClaimDraft(section="brand_overview", text="fabricated", chunk_id="does-not-exist")], context
    )

    metrics_text = client.get("/metrics").text
    assert 'smm_claims_rejected_total{section="brand_overview"}' in metrics_text
