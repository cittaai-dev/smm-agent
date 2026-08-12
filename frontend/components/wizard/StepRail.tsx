import Link from "next/link";
import type { ReactNode } from "react";

export interface WizardStepDef {
  title: string;
  desc: string;
}

export function StepRail({
  brandLabel,
  steps,
  currentIndex,
  maxVisitedIndex,
  stepHref,
  profileCard,
}: {
  brandLabel: string;
  steps: WizardStepDef[];
  currentIndex: number;
  maxVisitedIndex: number;
  stepHref: (index: number) => string | null;
  profileCard: ReactNode;
}) {
  return (
    <aside className="flex h-screen w-[280px] shrink-0 flex-col justify-between overflow-y-auto border-r border-border bg-surface px-5 py-7">
      <div>
        <div className="mb-7 flex items-center gap-2.5 px-2">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent font-mono text-sm font-bold text-white">
            S
          </div>
          <div className="text-sm font-semibold leading-tight">
            Signal
            <br />
            <span className="text-xs font-medium text-text-faint">{brandLabel}</span>
          </div>
        </div>
        <div className="flex flex-col">
          {steps.map((step, i) => {
            const isDone = i < currentIndex;
            const isCurrent = i === currentIndex;
            const href = i <= maxVisitedIndex && !isCurrent ? stepHref(i) : null;

            const circleClasses = isDone
              ? "bg-accent text-white border-transparent"
              : isCurrent
                ? "border-2 border-accent text-accent-text"
                : "border-2 border-border text-text-faint";
            const titleClasses = isCurrent
              ? "font-bold text-text"
              : isDone
                ? "font-semibold text-text"
                : "font-semibold text-text-faint";

            const row = (
              <div className="flex gap-3.5 rounded-lg px-2 py-1.5">
                <div className="flex flex-col items-center">
                  <div
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full font-mono text-[13px] font-bold ${circleClasses}`}
                  >
                    {isDone ? "✓" : i + 1}
                  </div>
                  {i < steps.length - 1 && (
                    <div
                      className={`my-1 min-h-[16px] w-0.5 flex-1 rounded ${isDone ? "bg-accent" : "bg-border"}`}
                    />
                  )}
                </div>
                <div className="pb-5">
                  <div className={`text-sm ${titleClasses}`}>{step.title}</div>
                  <div className="mt-0.5 text-xs text-text-faint">{step.desc}</div>
                </div>
              </div>
            );

            return href ? (
              <Link key={step.title} href={href} className="rounded-lg hover:bg-surface2">
                {row}
              </Link>
            ) : (
              <div key={step.title}>{row}</div>
            );
          })}
        </div>
      </div>
      {profileCard}
    </aside>
  );
}
