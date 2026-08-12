import { groupClaimsByField } from "@/lib/groupClaims";
import type { VerifiedClaim } from "@/lib/types";

const QUADRANTS: { key: string; label: string; bg: string; text: string }[] = [
  { key: "strength", label: "Strengths", bg: "bg-success-soft", text: "text-success" },
  { key: "weakness", label: "Weaknesses", bg: "bg-danger-soft", text: "text-danger" },
  { key: "opportunity", label: "Opportunities", bg: "bg-accent-soft", text: "text-accent-text" },
  { key: "threat", label: "Threats", bg: "bg-run-soft", text: "text-run" },
];

export function SwotGrid({ claims }: { claims: VerifiedClaim[] }) {
  const groups = groupClaimsByField(claims);

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="swot-grid">
      {QUADRANTS.map((q) => {
        const items = groups[q.key] ?? [];
        return (
          <div key={q.key} className={`rounded-lg p-4 ${q.bg}`}>
            <h3 className={`mb-2 font-semibold ${q.text}`}>{q.label}</h3>
            {items.length === 0 ? (
              <p className="text-sm text-text-faint">No verified findings yet.</p>
            ) : (
              <ul className="list-disc space-y-1 pl-4 text-sm text-text">
                {items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            )}
          </div>
        );
      })}
    </div>
  );
}
