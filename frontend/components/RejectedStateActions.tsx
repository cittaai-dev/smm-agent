"use client";

import { useState } from "react";
import type { DocumentStatus } from "@/lib/types";

// step5_trust_boundary.md §13: two distinct actions, since "fix something"
// means different things -- new evidence uploaded (rerun, regenerates from
// scratch) vs. the write-up was the problem (resubmit, re-enters review
// as-is). Only rendered once document.status === "rejected".
export function RejectedStateActions({
  status,
  onRerun,
  onResubmit,
  rerunPending,
  resubmitPending,
}: {
  status: DocumentStatus;
  onRerun: () => void;
  onResubmit: (note: string) => void;
  rerunPending?: boolean;
  resubmitPending?: boolean;
}) {
  const [note, setNote] = useState("");
  if (status !== "rejected") return null;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-run bg-run-soft p-4">
      <p className="text-sm font-medium text-text">This document was rejected — what changed?</p>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          className="rounded-md border border-border bg-bg px-3 py-1.5 text-sm font-medium disabled:opacity-40"
          disabled={rerunPending}
          onClick={onRerun}
        >
          {rerunPending ? "Re-running…" : "Re-run agent (new evidence uploaded)"}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <input
          className="min-w-64 flex-1 rounded border border-border px-2 py-1 text-sm"
          placeholder="How was this addressed via notes?"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <button
          type="button"
          className="rounded-md border border-border bg-bg px-3 py-1.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-40"
          disabled={!note.trim() || resubmitPending}
          onClick={() => onResubmit(note)}
        >
          {resubmitPending ? "Resubmitting…" : "Resubmit for review (addressed via notes)"}
        </button>
      </div>
    </div>
  );
}
