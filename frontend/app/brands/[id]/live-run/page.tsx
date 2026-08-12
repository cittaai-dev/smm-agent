"use client";

import { useMutation } from "@tanstack/react-query";
import { use } from "react";
import { collectNow } from "@/lib/api";
import { useDataCollectionStatus } from "@/hooks/useDataCollectionStatus";

const PHASES = [
  { name: "queued", label: "Queued" },
  { name: "competitor_sites", label: "Competitor sites" },
  { name: "youtube", label: "YouTube" },
  { name: "google_trends", label: "Google Trends" },
  { name: "newsapi", label: "NewsAPI" },
  { name: "completed", label: "Complete" },
];

// Step 6 Part B §4 -- watches workers/data_collection.py's per-source
// broadcast in real time (docs/implement/DATA_COLLECTION_QUICK_START.md §2).
export default function LiveRunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);
  const status = useDataCollectionStatus(brandId);

  const trigger = useMutation({
    mutationFn: () => collectNow(brandId),
  });

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-6">
      <h1 className="text-lg font-semibold text-text">Live Data Collection — {brandId}</h1>

      <button
        type="button"
        className="w-fit rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
        disabled={trigger.isPending}
        onClick={() => trigger.mutate()}
      >
        {trigger.isPending ? "Starting…" : "Start collection"}
      </button>

      <div className="flex flex-col gap-2">
        {PHASES.map((p) => {
          const reached = status.messages.some((m) => m.phase === p.name);
          const active = status.phase === p.name;
          return (
            <div
              key={p.name}
              className={`rounded p-3 text-sm ${
                active
                  ? "border-l-4 border-accent bg-accent-soft"
                  : reached
                    ? "bg-success-soft text-success"
                    : "bg-surface2 text-text-faint"
              }`}
            >
              {p.label}
              {active && <span className="ml-2 animate-pulse">…</span>}
            </div>
          );
        })}
      </div>

      <div className="h-48 overflow-y-auto rounded bg-text p-4 font-mono text-sm text-bg">
        {status.messages.length === 0 && <p className="text-text-faint">No status yet.</p>}
        {status.messages.map((m, i) => (
          <div key={i}>
            <span className="text-text-faint">[{new Date(m.timestamp).toLocaleTimeString()}]</span> {m.message}
          </div>
        ))}
      </div>

      <p className="font-mono text-xs text-text-dim">Items collected so far: {status.itemCount}</p>
    </div>
  );
}
