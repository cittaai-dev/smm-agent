import type { VerifiedClaim } from "@/lib/types";

// Flowing paragraph text, matching how docx_builder.py's _add_prose renders
// the same claims into the exported Word doc -- one paragraph per verified
// claim, no per-claim citation chrome. Raw citations still exist (see
// DocumentSectionsReview's collapsible "Show sources" detail) but don't
// dominate the read like the boxed ClaimCard view does.
export function ProseSection({ claims }: { claims: VerifiedClaim[] }) {
  const verified = claims.filter((c) => c.verified);

  if (verified.length === 0) {
    return <p className="text-sm text-text-faint">No verified findings yet.</p>;
  }

  return (
    <div className="flex flex-col gap-3 leading-relaxed text-text">
      {verified.map((claim, i) => (
        <p key={`${claim.claim_id}-${i}`}>{claim.text}</p>
      ))}
    </div>
  );
}
