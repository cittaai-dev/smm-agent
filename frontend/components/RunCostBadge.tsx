// Step 6 Part A §1 -- surfaced on the document review page next to a
// section's status. `usd` comes from MarketResearchDocument.cost_usd /
// SectionResult.cost_usd (backend/app/domain/cost.py's RunCostTracker,
// union-mode sections only for now -- see Deliverable.cost_usd's comment).
export function RunCostBadge({ usd, budget }: { usd: number; budget: number }) {
  const pct = budget > 0 ? (usd / budget) * 100 : 0;
  return (
    <span className="font-mono text-xs text-text-dim">
      ${usd.toFixed(3)} of ${budget.toFixed(2)}
      {pct > 80 && <span className="text-run"> ⚠</span>}
    </span>
  );
}
