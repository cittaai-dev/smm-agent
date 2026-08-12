import { groupClaimsByKey } from "@/lib/groupClaims";
import { FIELD_LABELS, SECTION_LAYOUT } from "@/lib/sectionLayout";
import type { VerifiedClaim } from "@/lib/types";

export function CompetitorTable({ claims }: { claims: VerifiedClaim[] }) {
  const layout = SECTION_LAYOUT.competitor_analysis;
  const groups = groupClaimsByKey(claims);
  const competitors = Object.keys(groups);

  if (competitors.length === 0) {
    return <p className="text-sm text-text-faint">No verified competitors yet.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] border-collapse text-sm" data-testid="competitor-table">
        <thead>
          <tr>
            <th className="border border-border bg-success px-3 py-2 text-left font-semibold text-white">
              Competitor
            </th>
            {layout.fields.map((field) => (
              <th
                key={field}
                className="border border-border bg-success px-3 py-2 text-left font-semibold text-white"
              >
                {FIELD_LABELS[field] ?? field}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {competitors.map((name) => (
            <tr key={name}>
              <td className="border border-border px-3 py-2 font-medium text-text">{name}</td>
              {layout.fields.map((field) => (
                <td key={field} className="border border-border px-3 py-2 text-text-dim">
                  {groups[name][field] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
