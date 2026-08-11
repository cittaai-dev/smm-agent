"use client";

import { useMutation } from "@tanstack/react-query";
import { use, useState } from "react";
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
  const [apiKey, setApiKey] = useState("");
  const status = useDataCollectionStatus(brandId, apiKey);

  const trigger = useMutation({
    mutationFn: () => collectNow(brandId),
  });

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-4 p-6">
      <h1 className="text-lg font-semibold text-slate-900">Live Data Collection — {brandId}</h1>

      <label className="flex flex-col gap-1 text-sm">
        API key
        <input
          className="rounded border border-slate-300 px-2 py-1"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
          placeholder="Your api key"
        />
      </label>

      <button
        type="button"
        className="w-fit rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
        disabled={!apiKey || trigger.isPending}
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
                  ? "border-l-4 border-blue-500 bg-blue-50"
                  : reached
                    ? "bg-emerald-50 text-emerald-800"
                    : "bg-slate-50 text-slate-400"
              }`}
            >
              {p.label}
              {active && <span className="ml-2 animate-pulse">…</span>}
            </div>
          );
        })}
      </div>

      <div className="h-48 overflow-y-auto rounded bg-slate-900 p-4 font-mono text-sm text-slate-100">
        {status.messages.length === 0 && <p className="text-slate-500">No status yet.</p>}
        {status.messages.map((m, i) => (
          <div key={i} className="text-slate-300">
            <span className="text-slate-500">[{new Date(m.timestamp).toLocaleTimeString()}]</span> {m.message}
          </div>
        ))}
      </div>

      <p className="text-xs text-slate-500">Items collected so far: {status.itemCount}</p>
    </div>
  );
}
