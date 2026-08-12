import { SECTION_LABELS } from "@/lib/sections";
import type { SectionResult } from "@/lib/types";
import { SectionStatusBadge } from "./SectionStatusBadge";

export function SectionRow({ section }: { section: SectionResult }) {
  const repaired = (section.call_site_trace.repair ?? 0) > 0;
  return (
    <div className="flex items-center justify-between rounded-lg border border-border p-4">
      <span className="font-medium text-text">{SECTION_LABELS[section.section]}</span>
      <div className="flex items-center gap-2">
        {repaired && (
          <span
            className="rounded-full bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent-text"
            title="This section's claims were re-tagged after an initial citation was rejected"
          >
            repair pass
          </span>
        )}
        <SectionStatusBadge status={section.status} claimsCount={section.claims.length} note={section.note} />
      </div>
    </div>
  );
}
