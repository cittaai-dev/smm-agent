"use client";

import { useQuery } from "@tanstack/react-query";
import { fetchDataSourceHealth } from "@/lib/api";
import type { DataSourceStatus } from "@/lib/types";

const STATUS_STYLE: Record<DataSourceStatus, string> = {
  ok: "border-emerald-500 bg-emerald-50",
  stale: "border-amber-500 bg-amber-50",
  never_run: "border-slate-300 bg-slate-50",
};

// Step 6 Part C §5 -- GET /health/data-sources, backed by collection_job_status
// (migration 0008). Reports every source in workers/data_collection.py's
// _COLLECTORS, including the still-unconfigured stubs, so a gap is visible
// rather than silently absent from the dashboard.
export function DataSourceHealth() {
  const { data, isLoading } = useQuery({
    queryKey: ["data-source-health"],
    queryFn: fetchDataSourceHealth,
    refetchInterval: 30_000,
  });

  if (isLoading || !data) {
    return <p className="text-sm text-slate-500">Loading data source health…</p>;
  }

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {Object.entries(data).map(([source, info]) => (
        <div key={source} className={`rounded-lg border-l-4 p-3 ${STATUS_STYLE[info.status]}`}>
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-900">{source}</span>
            <span className="text-xs uppercase tracking-wide text-slate-500">{info.status}</span>
          </div>
          <p className="mt-1 text-xs text-slate-600">
            {info.last_run
              ? `Last run ${new Date(info.last_run).toLocaleString()} (${info.staleness_hours?.toFixed(1)}h ago)`
              : "Never run"}
          </p>
          {info.error_rate_24h > 0.05 && (
            <p className="text-xs text-red-600">⚠ {(info.error_rate_24h * 100).toFixed(1)}% error rate (24h)</p>
          )}
          <p className="text-xs text-slate-500">{info.items_collected_24h} items collected (24h)</p>
        </div>
      ))}
    </div>
  );
}
