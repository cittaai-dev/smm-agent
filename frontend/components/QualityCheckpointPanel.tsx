import type { QualityCheckpoint } from "@/lib/types";

const ROWS: [keyof QualityCheckpoint, string][] = [
  ["all_sections_filled", "All sections filled"],
  ["competitor_count_ok", "At least 3 competitors analysed"],
  ["personas_grounded", "Personas grounded in real signals"],
  ["findings_lead_to_recommendations", "Findings lead to recommendations"],
];

// Mirrors SOP-1's own printed quality checkpoints verbatim -- a Team Lead
// reviewing the document sees the same checklist the SOP already asks them
// to apply manually, now computed server-side (GET .../checkpoint) rather
// than eyeballed. This panel never decides pass/fail itself: it renders
// whatever the server already evaluated, the same evaluate_checkpoint call
// that /approve enforces.
export function QualityCheckpointPanel({ checkpoint }: { checkpoint: QualityCheckpoint }) {
  const passed = ROWS.every(([key]) => checkpoint[key]);
  return (
    <div className="rounded-lg border border-slate-200 p-4" data-testid="quality-checkpoint-panel">
      <p className="mb-2 text-sm font-medium text-slate-900">Quality checkpoint</p>
      <div className="flex flex-col gap-1">
        {ROWS.map(([key, label]) => {
          const ok = checkpoint[key];
          return (
            <div key={key} className="flex items-center justify-between py-1 text-sm">
              <span className="text-slate-700">{label}</span>
              <span className={ok ? "text-green-700" : "text-slate-400"}>{ok ? "✓" : "—"}</span>
            </div>
          );
        })}
      </div>
      {!passed && (
        <p className="mt-2 text-xs text-amber-700">
          All checks must pass before this document can be approved.
        </p>
      )}
    </div>
  );
}
