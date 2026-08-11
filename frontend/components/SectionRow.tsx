import { SECTION_LABELS } from "@/lib/sections";
import type { SectionResult } from "@/lib/types";
import { SectionStatusBadge } from "./SectionStatusBadge";

export function SectionRow({ section }: { section: SectionResult }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-slate-200 p-4">
      <span className="font-medium text-slate-900">{SECTION_LABELS[section.section]}</span>
      <SectionStatusBadge status={section.status} claimsCount={section.claims.length} note={section.note} />
    </div>
  );
}
