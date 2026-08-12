"use client";

import { useQuery } from "@tanstack/react-query";
import { use } from "react";
import { getMarketSegment } from "@/lib/api";

export default function CompetitorsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);

  const segmentQuery = useQuery({
    queryKey: ["segment", brandId],
    queryFn: () => getMarketSegment("", brandId),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="mb-2.5 font-mono text-xs font-bold uppercase tracking-wide text-run">
          Step 4 / 6 · Competitor &amp; Market Analysis
        </div>
        <h1 className="text-[28px] font-bold">Competitor &amp; Market Analysis</h1>
        <p className="mt-2 max-w-xl text-text-dim">
          Live competitor discovery and relevance scoring isn&apos;t built yet — this step is tracked as
          a backlog item. What&apos;s real today is the market segment this brand is scoped to search
          within once discovery ships.
        </p>
      </div>

      {segmentQuery.isLoading && <p className="text-text-dim">Loading…</p>}
      {segmentQuery.data && (
        <div className="rounded-lg border border-border bg-surface p-4 text-sm">
          <div className="mb-2 font-semibold">{segmentQuery.data.segment_name || "Unnamed segment"}</div>
          <div className="text-text-dim">
            {segmentQuery.data.website_urls.length} whitelisted site
            {segmentQuery.data.website_urls.length === 1 ? "" : "s"} · max{" "}
            {segmentQuery.data.max_competitors_to_track} competitors to track
          </div>
          {segmentQuery.data.website_urls.length > 0 && (
            <ul className="mt-2 flex flex-col gap-1 font-mono text-xs text-text-dim">
              {segmentQuery.data.website_urls.map((url) => (
                <li key={url}>{url}</li>
              ))}
            </ul>
          )}
        </div>
      )}
      {segmentQuery.data === null && (
        <p className="text-sm text-text-faint">No market segment configured for this brand yet.</p>
      )}
      {segmentQuery.isError && (
        <p className="text-sm text-danger">Could not load market segment for this brand.</p>
      )}
    </div>
  );
}
