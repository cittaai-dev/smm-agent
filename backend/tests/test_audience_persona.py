from app.orchestration.graph import run_pipeline
from app.workers.ingest import ingest_file


def test_target_audience_run_populates_verified_personas(sample_file, fake_synthesize_with_personas):
    ingest_file(brand_id="test-brand", file_path=sample_file)

    result = run_pipeline(brand_id="test-brand", section="target_audience")

    assert result.deliverable.status == "pending_approval"
    assert result.personas
    [persona] = result.personas
    assert persona.verified
    assert persona.name == "Busy professional"
    assert persona.pain_points and persona.interests


def test_non_persona_section_never_populates_personas(sample_file, fake_synthesize_grounded):
    # brand_overview doesn't extract_audience_personas -- must stay empty,
    # not accidentally inherit target_audience's behavior.
    ingest_file(brand_id="test-brand", file_path=sample_file)

    result = run_pipeline(brand_id="test-brand", section="brand_overview")

    assert result.personas == []
    assert result.persona_drafts == []
