import { SECTION_ORDER } from "@/lib/sections";
import type { MarketResearchDocument } from "@/lib/types";
import { SectionRow } from "./SectionRow";

export function SectionOutline({ document }: { document: MarketResearchDocument }) {
  return (
    <div className="flex flex-col gap-2">
      {SECTION_ORDER.map((id) => {
        const section = document.sections[id];
        return section ? <SectionRow key={id} section={section} /> : null;
      })}
    </div>
  );
}
