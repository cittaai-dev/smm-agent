"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { use, type ReactNode } from "react";
import { WizardShell } from "@/components/wizard/WizardShell";
import { WorkspaceProfileCard } from "@/components/wizard/WorkspaceProfileCard";
import { BRAND_RUN_STEPS } from "@/lib/brandRunSteps";

// Steps 2 (research-plan) through 4 (synthesize) all review a completed
// run's output -- they need documentId, carried across steps as a query
// param since MarketResearchDocument only exists once /research/run-all
// (triggered from the "plan" step) has returned.
const STEPS_REQUIRING_RUN = [false, false, true, true, true];

export default function BrandRunLayout({
  children,
  params,
}: {
  children: ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id: brandId } = use(params);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const documentId = searchParams.get("documentId");

  const inGroupSteps = BRAND_RUN_STEPS.filter((s) => s.path !== "");
  const currentIndex = Math.max(
    0,
    inGroupSteps.findIndex((s) => pathname.endsWith(`/run/${s.path}`)),
  );
  const maxVisitedIndex = documentId ? BRAND_RUN_STEPS.length - 1 : 1;

  function pathFor(index: number): string {
    const qs = documentId ? `?documentId=${encodeURIComponent(documentId)}` : "";
    const step = BRAND_RUN_STEPS[index];
    if (step.path === "") {
      // Final step lives outside this route group, at the document's own id
      // -- carry brandId along so that page can rebuild the same wizard
      // shell (sidebar/stepper) without waiting on the document fetch to
      // learn its brand_id first.
      return documentId
        ? `/documents/${encodeURIComponent(documentId)}?from=run&brandId=${encodeURIComponent(brandId)}`
        : "";
    }
    return `/brands/${encodeURIComponent(brandId)}/run/${step.path}${qs}`;
  }

  function stepHref(index: number): string | null {
    const path = pathFor(index);
    return path || null;
  }

  const isLastInGroup = currentIndex === inGroupSteps.length - 1;
  const nextIndex = currentIndex + 1;
  const nextRequiresRun = STEPS_REQUIRING_RUN[nextIndex] ?? false;
  const nextDisabled = nextRequiresRun && !documentId;
  const nextHref = nextDisabled ? null : stepHref(nextIndex);

  return (
    <WizardShell
      brandLabel="Brand Run"
      pipelineBadge="BRAND WORKSPACE"
      scopeLabel={`brand:${brandId}`}
      steps={BRAND_RUN_STEPS}
      currentIndex={currentIndex}
      maxVisitedIndex={maxVisitedIndex}
      stepHref={stepHref}
      profileCard={<WorkspaceProfileCard />}
      backHref={currentIndex > 0 ? stepHref(currentIndex - 1) : null}
      nextHref={nextHref}
      nextLabel={isLastInGroup ? "Go to full report →" : "Next →"}
      nextDisabled={nextDisabled}
      nextHint={nextDisabled ? "Run research (Step 2) to continue" : undefined}
    >
      {children}
    </WizardShell>
  );
}
