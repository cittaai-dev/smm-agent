"use client";

import { useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { use } from "react";
import { runResearch } from "@/lib/api";

export default function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);
  const router = useRouter();

  const run = useMutation({
    mutationFn: () => runResearch(brandId),
    onSuccess: (deliverable) => {
      router.push(`/deliverables/${encodeURIComponent(deliverable.id)}`);
    },
  });

  return (
    <main className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Run Market Research</h1>
      <p className="text-slate-600">
        Brand: {brandId}. This runs Plan → Retrieve → Synthesize → Verify → Repair → Deliver for
        SOP-01 §1 (Brand overview).
      </p>

      <button
        type="button"
        className="w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        onClick={() => run.mutate()}
        disabled={run.isPending}
      >
        {run.isPending ? "Running…" : "Run research"}
      </button>

      {run.isError && (
        <p className="text-sm text-red-700">Run failed: {(run.error as Error).message}</p>
      )}
    </main>
  );
}
