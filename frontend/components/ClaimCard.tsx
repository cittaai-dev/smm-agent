import type { VerifiedClaim } from "@/lib/types";

const REASON_LABELS: Record<string, string> = {
  missing_chunk: "Citation does not resolve to any retrieved chunk",
  no_citation: "No citation was provided",
};

export function ClaimCard({ claim }: { claim: VerifiedClaim }) {
  const borderColor = claim.verified ? "border-green-500" : "border-red-500";
  return (
    <div className={`rounded-lg border-2 p-4 ${borderColor}`} data-testid="claim-card">
      <p className="text-slate-900">{claim.text}</p>
      <div className="mt-2 flex items-center gap-2 text-xs text-slate-500">
        <code className="rounded bg-slate-100 px-1.5 py-0.5">{claim.chunk_id || "no chunk_id"}</code>
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
