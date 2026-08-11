"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use } from "react";
import { listSources, runAllResearch } from "@/lib/api";

const STATUS_COLOR: Record<string, string> = {
  degraded: "text-orange-700",
  ingested: "text-green-700",
  uploading: "text-slate-500",
};

export default function PlanPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);
  const router = useRouter();

  // Running research before ingest finishes is a real, previously-hit bug
  // (Run clicked while Celery was still chunking/embedding -> a section reads
  // as "insufficient_grounding" even though the source material was fine) --
  // poll and gate the button on it rather than trusting the user to wait.
  const sources = useQuery({
    queryKey: ["sources", brandId],
    queryFn: () => listSources(brandId),
    refetchInterval: (query) =>
      query.state.data?.some((s) => s.status === "uploading") ? 2000 : false,
  });

  const run = useMutation({
    mutationFn: () => runAllResearch(brandId),
    onSuccess: (document) => {
      router.push(`/documents/${encodeURIComponent(document.id)}`);
    },
  });

  const stillIngesting = sources.data?.some((s) => s.status === "uploading") ?? false;

  return (
    <main className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Run Market Research</h1>
      <p className="text-slate-600">
        Brand: {brandId}. Runs Plan → Retrieve → Synthesize → Verify → Repair → Deliver across all 11
        SOP-01 sections.
      </p>

      {sources.data && sources.data.length > 0 && (
        <ul className="flex flex-col gap-1 text-sm">
          {sources.data.map((s) => (
            <li
              key={s.file_id}
              className="flex items-center justify-between rounded border border-slate-200 px-3 py-2"
            >
              <span>{s.filename}</span>
              <span className={STATUS_COLOR[s.status] ?? "text-slate-500"}>
                {s.status}
                {s.degraded_reason ? ` — ${s.degraded_reason}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}

      <button
        type="button"
        className="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        onClick={() => run.mutate()}
        disabled={run.isPending || stillIngesting}
      >
        {run.isPending ? "Running…" : stillIngesting ? "Waiting for ingest…" : "Run research"}
      </button>

      {run.isError && <p className="text-sm text-red-700">Run failed: {(run.error as Error).message}</p>}
    </main>
  );
}
