import Link from "next/link";
import type { ReactNode } from "react";
import { StepRail, type WizardStepDef } from "./StepRail";

export function WizardShell({
  brandLabel,
  pipelineBadge,
  scopeLabel,
  steps,
  currentIndex,
  maxVisitedIndex,
  stepHref,
  profileCard,
  backHref,
  nextHref,
  nextLabel = "Next →",
  nextDisabled,
  nextHint,
  children,
}: {
  brandLabel: string;
  pipelineBadge: string;
  scopeLabel: string;
  steps: WizardStepDef[];
  currentIndex: number;
  maxVisitedIndex: number;
  stepHref: (index: number) => string | null;
  profileCard: ReactNode;
  backHref: string | null;
  nextHref: string | null;
  nextLabel?: string;
  nextDisabled?: boolean;
  nextHint?: string;
  children: ReactNode;
}) {
  const total = steps.length;
  const pct = total > 1 ? (currentIndex / (total - 1)) * 100 : 0;

  return (
    <div className="fixed inset-0 z-40 flex bg-bg text-text">
      <StepRail
        brandLabel={brandLabel}
        steps={steps}
        currentIndex={currentIndex}
        maxVisitedIndex={maxVisitedIndex}
        stepHref={stepHref}
        profileCard={profileCard}
      />

      <div className="flex flex-1 flex-col overflow-hidden">
        <div className="flex h-16 shrink-0 items-center justify-between border-b border-border px-10">
          <div className="flex items-center gap-2.5">
            <span className="rounded bg-run-soft px-2 py-0.5 font-mono text-xs tracking-wide text-run">
              {pipelineBadge}
            </span>
            <span className="font-mono text-[13.5px] text-text-dim">{scopeLabel}</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="font-mono text-xs text-text-faint">
              STEP {currentIndex + 1} / {total}
            </span>
            <div className="h-1 w-[140px] overflow-hidden rounded-full bg-border">
              <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
            </div>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[880px] px-10 pb-14 pt-12">{children}</div>
        </div>

        <div className="flex shrink-0 items-center justify-between border-t border-border px-10 py-4">
          {backHref ? (
            <Link
              href={backHref}
              className="rounded-md border border-border px-4 py-2 text-sm text-text-dim hover:border-text-faint"
            >
              ← Back
            </Link>
          ) : (
            <div />
          )}

          <div className="flex flex-col items-end gap-1">
            <span className="font-mono text-xs text-text-faint">
              STEP {currentIndex + 1} OF {total}
            </span>
            {nextDisabled && nextHint && <span className="text-xs text-text-faint">{nextHint}</span>}
          </div>

          {nextHref && !nextDisabled ? (
            <Link
              href={nextHref}
              className="rounded-md bg-accent px-5 py-2 text-sm font-bold text-white hover:opacity-90"
            >
              {nextLabel}
            </Link>
          ) : (
            <button
              type="button"
              disabled
              className="rounded-md bg-accent px-5 py-2 text-sm font-bold text-white opacity-40"
            >
              {nextLabel}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
