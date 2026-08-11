import type { BridgePair, VerifiedClaim } from "@/lib/types";
import { ClaimCard } from "./ClaimCard";

// Extends the ClaimCard family for BRIDGE mode's two-source claims
// (competitor_analysis, platform_analysis): a claim here cites both an
// observed run chunk and a Market Intel Core benchmark chunk, so the reader
// needs to see the comparison, not just the resulting text.
export function BridgePairCard({ pair, claim }: { pair: BridgePair; claim?: VerifiedClaim }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4" data-testid="bridge-pair-card">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Observed (brand data)</p>
      <p className="mb-3 mt-1 text-sm text-slate-900">{pair.run_chunk.text}</p>
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
        Market Intel Core benchmark
      </p>
      <p className="mt-1 text-sm text-slate-900">{pair.core_chunk.text}</p>
      {claim && (
        <div className="mt-4 border-t border-slate-100 pt-4">
          <ClaimCard claim={claim} />
        </div>
      )}
    </div>
  );
}
