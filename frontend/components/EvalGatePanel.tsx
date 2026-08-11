import type { EvalGateResult } from "@/lib/types";

const ROWS: [keyof EvalGateResult, string, string][] = [
  ["citation_rejection_rate", "Citation rejection rate", "max_citation_rejection_rate"],
  ["degraded_ratio", "Degraded chunk ratio", "max_degraded_ratio"],
  ["l0_ratio", "L0-only chunk ratio", "max_l0_ratio"],
];

// Renders whatever the server already decided (POST .../promotion-requests
// evaluates and returns this) -- never re-derives pass/fail on the frontend,
// same discipline as QualityCheckpointPanel deferring to evaluate_checkpoint.
export function EvalGatePanel({ result }: { result: EvalGateResult }) {
  return (
    <div className="rounded-lg border border-slate-200 p-4" data-testid="eval-gate-panel">
      <p className="mb-2 text-sm font-medium text-slate-900">Eval gate</p>
      <div className="flex flex-col gap-1">
        {ROWS.map(([key, label, thresholdKey]) => {
          const value = result[key] as number;
          const threshold = result.thresholds[thresholdKey];
          const ok = value <= threshold;
          return (
            <div key={key} className="flex items-center justify-between py-1 text-sm">
              <span className="text-slate-700">{label}</span>
              <span className={ok ? "text-green-700" : "text-red-700"}>
                {(value * 100).toFixed(1)}%{" "}
                <span className="text-xs text-slate-400">(max {(threshold * 100).toFixed(0)}%)</span>
              </span>
            </div>
          );
        })}
        <div className="flex items-center justify-between py-1 text-sm">
          <span className="text-slate-700">Coverage</span>
          <span className={result.coverage_ok ? "text-green-700" : "text-red-700"}>
            {result.coverage_ok ? "✓ adequate" : "✗ insufficient"}
          </span>
        </div>
      </div>
      <p className={`mt-2 text-xs font-medium ${result.passed ? "text-green-700" : "text-amber-700"}`}>
        {result.passed ? "Eligible for promotion" : "Blocked -- fix the corpus and re-request promotion"}
      </p>
    </div>
  );
}
