"use client";

import { useSearchParams } from "next/navigation";
import { RESEARCH_PLAN_SECTIONS, type EvidencePill } from "@/lib/researchPlan";

const PILL_TONE: Record<EvidencePill["tone"], string> = {
  neutral: "bg-surface2 text-text-dim",
  core: "bg-success-soft text-success",
  lead: "bg-accent-soft text-accent-text",
  synth: "bg-surface2 text-text-faint",
};

export default function ResearchPlanPage() {
  const searchParams = useSearchParams();
  const documentId = searchParams.get("documentId");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="mb-2.5 font-mono text-xs font-bold uppercase tracking-wide text-run">
          Step 3 / 6 · Research Plan
        </div>
        <h1 className="text-[28px] font-bold">Research Plan</h1>
        <p className="mt-2 max-w-xl text-text-dim">
          Before drafting anything, the agent lays out the same market research document the team fills
          in for every brand, and maps each section to where its evidence will come from.
        </p>
      </div>

      <div>
        <div className="mb-2.5 text-xs font-semibold text-text-faint">
          MARKET RESEARCH DOCUMENT — OUTLINE
        </div>
        <div className="flex flex-col gap-1.5">
          {RESEARCH_PLAN_SECTIONS.map((sec) => (
            <div
              key={sec.id}
              className="flex items-center gap-3.5 rounded-lg border border-border bg-surface px-4 py-2.5"
            >
              <div className="w-5 shrink-0 font-mono text-xs text-text-faint">{sec.n}</div>
              <div className="min-w-[180px] flex-1 text-sm font-semibold">{sec.title}</div>
              <div className="flex flex-wrap justify-end gap-1.5">
                {sec.pills.map((pill) => (
                  <span
                    key={pill.label}
                    className={`whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[11px] ${PILL_TONE[pill.tone]}`}
                  >
                    {pill.label}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {!documentId && (
        <p className="text-sm text-text-faint">
          This outline reflects how every brand run is structured — it&apos;s the same before or after
          this run finishes.
        </p>
      )}
    </div>
  );
}
