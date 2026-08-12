import { groupClaimsByKey } from "@/lib/groupClaims";
import { FIELD_LABELS, PLATFORM_NAMES, SECTION_LAYOUT } from "@/lib/sectionLayout";
import type { VerifiedClaim } from "@/lib/types";

export function PlatformTable({ claims }: { claims: VerifiedClaim[] }) {
  const layout = SECTION_LAYOUT.platform_analysis;
  const groups = groupClaimsByKey(claims);

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-sm" data-testid="platform-table">
        <thead>
          <tr>
            <th className="border border-border bg-success px-3 py-2 text-left font-semibold text-white">
              Platform
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
          {/* Every platform renders, even with no claims yet -- P5 degrade-not-fail
              applied to the UI: an empty row is honest, a missing one looks broken. */}
          {PLATFORM_NAMES.map((platform) => (
            <tr key={platform}>
              <td className="border border-border px-3 py-2 font-medium text-text">{platform}</td>
              {layout.fields.map((field) => (
                <td key={field} className="border border-border px-3 py-2 text-text-dim">
                  {groups[platform]?.[field] ?? ""}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
