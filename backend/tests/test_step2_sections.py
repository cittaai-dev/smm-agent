from app.domain.sop1 import SECTIONS_BY_ID, SOP1_SECTIONS
from app.orchestration.graph import run_pipeline
from app.orchestration.section_runner import run_section
from app.workers.ingest import ingest_file

_CORE_DEPENDENT_SECTIONS = [s.id for s in SOP1_SECTIONS if s.requires_core]


def test_union_mode_generalizes_to_a_second_section(sample_file, fake_synthesize_grounded):
    # Step 1 proved this only for brand_overview -- the whole point of the Step 2
    # registry is that the same graph now works for any union-mode section.
    ingest_file(brand_id="test-brand", file_path=sample_file)

    result = run_pipeline(brand_id="test-brand", section="target_audience")

    assert result.deliverable.status == "pending_approval"
    assert all(c.section == "target_audience" for c in result.deliverable.claims)
    assert result.deliverable.id == "del-test-brand-target_audience"


def test_run_section_union_mode_maps_pending_approval_to_verified(sample_file, fake_synthesize_grounded):
    ingest_file(brand_id="test-brand", file_path=sample_file)
    spec = SECTIONS_BY_ID["customer_needs"]

    result = run_section("test-brand", spec, prior={})

    assert result.status == "verified"
    assert result.section == "customer_needs"
    assert result.claims


def test_run_section_union_mode_maps_insufficient_grounding_to_insufficient_evidence(
    sample_file, fake_synthesize_empty
):
    ingest_file(brand_id="test-brand", file_path=sample_file)
    spec = SECTIONS_BY_ID["customer_needs"]

    result = run_section("test-brand", spec, prior={})

    assert result.status == "insufficient_evidence"
    assert result.claims == []


def test_core_dependent_sections_degrade_cleanly_without_any_llm_call():
    # market_overview, competitor_analysis, platform_analysis, trends_opportunities --
    # Market Intel Core doesn't exist until Step 4 (P5: degrade, never fail).
    # No brand material is ingested here at all -- the point is that these
    # sections short-circuit before ever touching retrieval or an LLM call site,
    # so there's nothing to mock and nothing that could accidentally succeed.
    assert len(_CORE_DEPENDENT_SECTIONS) == 4
    for section_id in _CORE_DEPENDENT_SECTIONS:
        spec = SECTIONS_BY_ID[section_id]
        result = run_section("brand-no-core", spec, prior={})

        assert result.status == "insufficient_evidence", section_id
        assert result.claims == []
        assert result.call_site_trace == {}
        assert "Step 4" in result.note


def test_direct_input_section_degrades_when_nothing_submitted():
    spec = SECTIONS_BY_ID["business_goals"]

    result = run_section("brand-no-input", spec, prior={})

    assert result.status == "insufficient_evidence"
    assert result.claims == []


def test_direct_input_section_is_team_provided_once_submitted():
    from app.infra.db import get_session

    with get_session() as session:
        session.execute(
            """INSERT INTO team_input (brand_id, section, text, author)
               VALUES ('brand-x', 'business_goals', 'Grow DTC revenue 20% YoY.', 'jane@agency.com')"""
        )
        session.commit()

    spec = SECTIONS_BY_ID["business_goals"]
    result = run_section("brand-x", spec, prior={})

    assert result.status == "team_provided"
    [claim] = result.claims
    assert claim.verified
    assert claim.text == "Grow DTC revenue 20% YoY."


def test_team_input_api_rejects_non_direct_input_section():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.put(
        "/brands/brand-x/sections/brand_overview/team-input",
        json={"text": "should be rejected"},
    )
    assert response.status_code == 422


def test_team_input_api_round_trips_into_section_runner():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.put(
        "/brands/brand-x/sections/business_goals/team-input",
        json={"text": "Expand into Canada by Q4.", "author": "jane@agency.com"},
    )
    assert response.status_code == 200

    spec = SECTIONS_BY_ID["business_goals"]
    result = run_section("brand-x", spec, prior={})
    assert result.status == "team_provided"
    assert result.claims[0].text == "Expand into Canada by Q4."
