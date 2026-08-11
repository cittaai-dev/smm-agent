import type { VerifiedClaim } from "@/lib/types";

const REASON_LABELS: Record<string, string> = {
  missing_chunk: "Citation does not resolve to any retrieved chunk",
  no_citation: "No citation was provided",
  missing_source_claim: "Cites an upstream claim that was itself rejected",
  no_source_claims: "No upstream claim was cited",
};

// A claim cites either a raw evidence chunk_id (union-mode sections) or a set
// of upstream claim_ids (synthesis_only sections, e.g. SWOT deriving from
// brand_overview) -- never both. Showing "no chunk_id" for a properly-cited
// derived claim would misreport it as uncited.
function citationLabel(claim: VerifiedClaim): string {
  if (claim.chunk_id) return claim.chunk_id;
  if (claim.source_claim_ids.length > 0) {
    return `derived from ${claim.source_claim_ids.length} upstream claim${claim.source_claim_ids.length > 1 ? "s" : ""}`;
  }
  return "no citation";
}

export function ClaimCard({ claim }: { claim: VerifiedClaim }) {
  const borderColor = claim.verified ? "border-green-500" : "border-red-500";
  return (
    <div className={`rounded-lg border-2 p-4 ${borderColor}`} data-testid="claim-card">
      <p className="text-slate-900">{claim.text}</p>
      <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
        <code className="rounded bg-slate-100 px-1.5 py-0.5">{citationLabel(claim)}</code>
        {claim.verified ? (
          <span className="text-green-700">verified</span>
        ) : (
          <span className="text-red-700">
            rejected — {REASON_LABELS[claim.rejection_reason ?? ""] ?? claim.rejection_reason}
          </span>
        )}
      </div>
    </div>
  );
}
