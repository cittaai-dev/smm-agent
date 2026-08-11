from dataclasses import dataclass

from app.domain.chunk import Chunk
from app.ingestion.router import L0_CONFIDENCE_CEILING


@dataclass
class ValidationResult:
    code: str
    passed: bool
    detail: str = ""


def validate_batch(chunks: list[Chunk]) -> list[ValidationResult]:
    """Never raises -- every check returns pass/fail (P5: a validator that
    throws would turn a degrade path into a hard failure)."""
    return [
        _c1_atomicity(chunks),
        _c2_heading_path_stamped(chunks),
        _c3_total_order(chunks),
        _c4_monotonic_escalation(chunks),
        _c5_determinism(chunks),
        _c6_degrade_not_fail(),
        _c7_order_stamped(chunks),
        _c8_edge_confinement(),
    ]


def _c1_atomicity(chunks: list[Chunk]) -> ValidationResult:
    ok = all(len(c.text.strip()) > 0 for c in chunks)
    return ValidationResult("C1", ok, "empty chunk found" if not ok else "")


def _c2_heading_path_stamped(chunks: list[Chunk]) -> ValidationResult:
    ok = all(isinstance(c.heading_path, list) for c in chunks)
    return ValidationResult("C2", ok, "heading_path not stamped" if not ok else "")


def _c3_total_order(chunks: list[Chunk]) -> ValidationResult:
    spans = [c.block_span for c in chunks]
    ok = spans == sorted(spans)
    return ValidationResult("C3", ok, "spans not strictly ordered" if not ok else "")


def _c4_monotonic_escalation(chunks: list[Chunk]) -> ValidationResult:
    # A degraded (L0) chunk must never carry structural-parse-level confidence --
    # strategy and confidence have to agree, or a downstream reader can't trust
    # order_confidence to mean what it claims (P7).
    ok = all((not c.degraded) or c.order_confidence <= L0_CONFIDENCE_CEILING for c in chunks)
    return ValidationResult("C4", ok, "degraded chunk claims non-degraded confidence" if not ok else "")


def _c5_determinism(chunks: list[Chunk]) -> ValidationResult:
    ids = [c.chunk_id for c in chunks]
    ok = len(ids) == len(set(ids))
    return ValidationResult("C5", ok, "duplicate chunk_id within batch" if not ok else "")


def _c6_degrade_not_fail() -> ValidationResult:
    # Not a per-chunk predicate -- C6 is the policy that a validate_batch()
    # failure routes back to route_and_chunk(force_l0=True) rather than aborting
    # the ingest (see workers/ingest.py). Kept in the result list so a review of
    # "which invariants did this batch satisfy" is complete, not because there's
    # a chunk-level condition to check here.
    return ValidationResult("C6", True)


def _c7_order_stamped(chunks: list[Chunk]) -> ValidationResult:
    ok = all(c.order_confidence is not None for c in chunks)
    return ValidationResult("C7", ok, "order_confidence missing" if not ok else "")


def _c8_edge_confinement() -> ValidationResult:
    # No cross-KB edges exist yet in Step 2 (Brand Workspace only, no Core) --
    # trivially passes. Real check (run:x -> core:y only, never core -> run)
    # lands with Step 4's Core builder.
    return ValidationResult("C8", True)
