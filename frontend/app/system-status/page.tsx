"use client";

import { useQuery } from "@tanstack/react-query";
import { API_BASE_URL } from "@/lib/api";
import { DataSourceHealth } from "@/components/DataSourceHealth";

async function fetchHealth(path: string): Promise<{ status: string } | null> {
  try {
    const res = await fetch(`${API_BASE_URL}${path}`);
    return res.ok ? await res.json() : null;
  } catch {
    return null;
  }
}

// Step 6 Part C §10 -- operator-facing operational visibility. Deliberately
// doesn't fabricate a p95-latency/citation-rejection-rate summary here: those
// live in Prometheus (/metrics, infra/telemetry.py) behind real Grafana
// queries once one is deployed, not recomputed ad hoc in the frontend from
// data it doesn't have.
export default function SystemStatusPage() {
  const live = useQuery({ queryKey: ["health", "live"], queryFn: () => fetchHealth("/health/live") });
  const ready = useQuery({ queryKey: ["health", "ready"], queryFn: () => fetchHealth("/health/ready") });

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-lg font-semibold text-text">System Status</h1>
        <p className="text-sm text-text-dim">Operator-facing health and data collection visibility.</p>
      </div>

      <div className="flex gap-4">
        <StatusPill label="API liveness" ok={live.data?.status === "alive"} />
        <StatusPill label="API readiness (DB + Redis)" ok={ready.data?.status === "ready"} />
      </div>

      <div>
        <h2 className="mb-2 text-sm font-semibold text-text">Data sources</h2>
        <DataSourceHealth />
      </div>

      <p className="text-xs text-text-faint">
        Full metrics (citation rejection rate, run latency, cost per run, call-site counts):{" "}
        <a className="underline" href={`${API_BASE_URL}/metrics`}>
          {API_BASE_URL}/metrics
        </a>
      </p>
    </div>
  );
}

function StatusPill({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className={`rounded-md border px-3 py-1.5 text-sm ${ok ? "border-success bg-success-soft" : "border-danger bg-danger-soft"}`}>
      {label}: <span className="font-medium">{ok ? "ok" : "down"}</span>
    </div>
  );
}
