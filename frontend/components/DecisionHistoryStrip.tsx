import type { ApprovalEvent } from "@/lib/types";

// step5_trust_boundary.md Part C: a reject-then-reapprove sequence is now
// preserved as multiple approval_event rows, not overwritten -- this is the
// component that makes that provenance visible instead of free once the data
// model stopped discarding it.
export function DecisionHistoryStrip({ events }: { events: ApprovalEvent[] }) {
  if (events.length === 0) return null;
  return (
    <div className="flex flex-col gap-1 text-xs text-text-dim" data-testid="decision-history">
      {events.map((e) => (
        <div key={e.id ?? `${e.decision}-${e.decided_at}`}>
          <span className="font-medium capitalize">{e.decision}</span> by {e.approver_id}
          {e.decided_at && <> — {new Date(e.decided_at).toLocaleString()}</>}
          {e.note && <>: {e.note}</>}
        </div>
      ))}
    </div>
  );
}
