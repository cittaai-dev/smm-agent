---
name: tdd-policy
description: "User's testing preference for smm-agent — TDD with minimal effort, integration-tests-first, unit tests reserved for core/pure logic only"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 3c2927fc-d3fc-4131-94ed-20459d6449d7
  modified: 2026-08-10T23:53:04.972Z
---

For smm-agent, write tests test-first but keep total test *volume* minimal — bias heavily toward
integration tests over a large unit-test suite.

**Why:** the user asked explicitly (2026-08-11) to "improve code producing and feature running on test
driven development with minimal effort on the tests with more focus on integration with minimal to core
unit testing only" — i.e. tests should prove the pipeline works end-to-end, not exhaustively cover every
function in isolation. This also matches the project's own acceptance-test style in
`docs/implement/step1_foundation.md §10` / `step2 §10` / `step3 §9` — each step's "definition of done" is a
short list of pipeline-level tests (`test_citation_resolves`, `test_idempotent_reupload`,
`test_approval_gate_blocks_default`), not unit tests per function.

**How to apply:**
- Default to an integration test that drives a real code path (e.g. `run_pipeline(brand_id=...)` through
  Plan→Retrieve→Synthesize→Verify→Deliver, or a FastAPI `TestClient` hitting a real endpoint against a real
  test DB) over mocking every collaborator.
- Reserve unit tests for genuinely pure, deterministic core logic where an integration test would be slow
  or indirect to exercise the edge case: [[engineering-principles]] items 1–4 are the prime candidates —
  `verify_claims` (citation resolution / rejection reasons), the C1–C8 validators, RRF fusion math,
  `QualityCheckpoint.passed`, content-hash idempotency.
- Don't write a unit test for something an integration test already exercises just for "coverage." One
  well-chosen integration test per acceptance criterion beats five unit tests mocking the same path.
- Each step's own acceptance-test list (Step 1 §10, Step 2 §10, Step 3 §9) is the target test suite for that
  step — implement those first, add more only if a real bug demonstrates a gap.
- LLM call sites (Plan/Synthesize/Repair) should be tested through fixtures/golden cases
  (`dev_guidelines.md §9` eval harness pattern) rather than mocked unit-by-unit — this is itself closer to
  an integration test of the prompt+parsing contract than a unit test of code logic.
