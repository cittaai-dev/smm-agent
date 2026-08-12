import { SECTION_DESCRIPTIONS } from "@/lib/sectionDescriptions";
import { SECTION_LABELS, SECTION_ORDER } from "@/lib/sections";
import { SECTION_LAYOUT } from "@/lib/sectionLayout";
import type { MarketResearchDocument, VerifiedClaim } from "@/lib/types";
import { ClaimList } from "./ClaimList";
import { PersonaList } from "./PersonaList";
import { CompetitorTable } from "./document-sections/CompetitorTable";
import { PersonaTable } from "./document-sections/PersonaTable";
import { PlatformTable } from "./document-sections/PlatformTable";
import { SwotGrid } from "./document-sections/SwotGrid";

export function DocumentSectionsReview({ document }: { document: MarketResearchDocument }) {
  return (
    <div className="flex flex-col gap-8">
      {SECTION_ORDER.map((id, index) => {
        const section = document.sections[id];
        const layout = SECTION_LAYOUT[id];
        const hasContent = !!section && (section.claims.length > 0 || section.personas.length > 0);

        // Structured sections always render their table/grid skeleton (even
        // with no data yet, matching docx_builder.py's identical decision for
        // platform_analysis's fixed row set) -- prose sections stay hidden
        // when genuinely empty, same behavior as before this change.
        if (!layout.structuredOutput && !hasContent) return null;

        const claims = section?.claims ?? [];
        const personas = section?.personas ?? [];

        return (
          <div key={id} className="flex flex-col gap-2">
            <h2 className="text-lg font-semibold text-text">
              {index + 1}. {SECTION_LABELS[id]}
            </h2>
            <p className="-mt-1 text-sm italic text-text-faint">{SECTION_DESCRIPTIONS[id]}</p>

            {id === "target_audience" ? (
              <>
                <ClaimList claims={claims} />
                <PersonaTable personas={personas} />
              </>
            ) : layout.structuredOutput === "competitor_table" ? (
              <>
                <CompetitorTable claims={claims} />
                <CitationDetails claims={claims} />
              </>
            ) : layout.structuredOutput === "platform_table" ? (
              <>
                <PlatformTable claims={claims} />
                <CitationDetails claims={claims} />
              </>
            ) : layout.structuredOutput === "swot_grid" ? (
              <>
                <SwotGrid claims={claims} />
                <CitationDetails claims={claims} />
              </>
            ) : (
              <>
                <ClaimList claims={claims} />
                <PersonaList personas={personas} />
              </>
            )}
          </div>
        );
      })}
    </div>
  );
}

function CitationDetails({ claims }: { claims: VerifiedClaim[] }) {
  if (claims.length === 0) return null;
  return (
    <details className="text-sm">
      <summary className="cursor-pointer text-text-faint">Show per-cell citations</summary>
      <div className="mt-2">
        <ClaimList claims={claims} />
      </div>
    </details>
  );
}
