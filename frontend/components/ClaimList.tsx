import type { VerifiedClaim } from "@/lib/types";
import { ClaimCard } from "./ClaimCard";

export function ClaimList({ claims }: { claims: VerifiedClaim[] }) {
  if (claims.length === 0) {
    return <p className="text-text-dim">No claims yet.</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      {claims.map((claim, i) => (
        <ClaimCard key={`${claim.chunk_id}-${i}`} claim={claim} />
      ))}
    </div>
  );
}
