# Testing policy

TDD with minimal test volume. The goal is confidence that the pipeline works, not coverage percentage.

## Bias: integration over unit

Default to an integration test that drives a real code path — `run_pipeline(brand_id=...)` through
Plan→Retrieve→Synthesize→Verify→Deliver, or a FastAPI `TestClient` hitting a real endpoint against a real
test database (a disposable Postgres, not mocks). One well-chosen integration test per acceptance criterion
beats five unit tests mocking the same collaborators.

## Where unit tests earn their keep

Only for pure, deterministic core logic where an integration test would be slow or indirect to exercise the
edge case:

- `verify_claims` — citation resolution and each rejection reason (`missing_chunk`, `no_citation`)
- C1–C8 ingest validators, especially C6 (degrade-not-fail) and C3 (total order)
- RRF fusion math (`_rrf_fuse`)
- `QualityCheckpoint.passed` and `evaluate_checkpoint`
- content-hash idempotency helpers

## LLM call sites

Test Plan/Synthesize/Repair through fixtures and golden cases (`dev_guidelines.md §9` eval harness pattern:
`tests/golden/`), not by mocking the LLM client function-by-function. A golden case run through the real
prompt-render + parse path is itself closer to an integration test of the prompt contract.

## Per-step target suite

Each build step in `docs/implement/` ends with its own acceptance-test list — implement that list first,
before writing any additional tests:

- Step 1: `step1_foundation.md §10` — `test_citation_resolves`, `test_fabricated_citation_rejected`,
  `test_idempotent_reupload`, `test_approval_gate_blocks_default`.
- Step 2: `step2_ingest_hardening.md §10` — file-type ingest, scanned-image degrade, Core-dependent section
  degrade, brand-only section completion, cross-file-type reupload no-op.
- Step 3: `step3_retrieval_generation.md §9` — hybrid recall vs dense-only, bounded repair, approval/
  distribution gate enforcement, rerank cache hit.

Add a test beyond these lists only when a real bug demonstrates a gap the list didn't cover.

## Call-site budget test

Per `dev_guidelines.md §7`: one test asserts `_call_counts` at the end of every pipeline run so a future 4th
LLM call site fails CI immediately, not a design review six months later.
