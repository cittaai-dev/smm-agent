"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { use, useState } from "react";
import {
  getMarketSegment,
  listDataSourceCredentials,
  saveDataSourceCredential,
  setMarketSegment,
} from "@/lib/api";
import type { DataSourceKind } from "@/lib/types";

const SOURCES: DataSourceKind[] = ["google_trends", "newsapi", "youtube", "scrapy_competitor"];

// Step 5 Part D: per-brand data source credentials + market segment
// whitelist. Local dev (SMM_AUTH_DEV_BYPASS) skips the platform api-key/
// brand-grant check server-side, so there's no key input here anymore --
// lib/api.ts's withApiKey supplies a dev-only default. A real login flow
// replacing this is still out of scope.
export default function BrandSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);
  const queryClient = useQueryClient();

  const credentialsQuery = useQuery({
    queryKey: ["credentials", brandId],
    queryFn: () => listDataSourceCredentials("", brandId),
  });

  const segmentQuery = useQuery({
    queryKey: ["segment", brandId],
    queryFn: () => getMarketSegment("", brandId),
  });

  const [source, setSource] = useState<DataSourceKind>("newsapi");
  const [sourceApiKey, setSourceApiKey] = useState("");
  const [rateLimit, setRateLimit] = useState(60);

  const saveCredential = useMutation({
    mutationFn: () => saveDataSourceCredential("", brandId, source, sourceApiKey, rateLimit),
    onSuccess: () => {
      setSourceApiKey("");
      queryClient.invalidateQueries({ queryKey: ["credentials", brandId] });
    },
  });

  const [segmentName, setSegmentName] = useState("");
  const [websiteUrls, setWebsiteUrls] = useState("");
  const [youtubeKeywords, setYoutubeKeywords] = useState("");
  const [maxCompetitors, setMaxCompetitors] = useState(10);

  const saveSegment = useMutation({
    mutationFn: () =>
      setMarketSegment("", brandId, {
        segment_name: segmentName,
        website_urls: websiteUrls.split(",").map((s) => s.trim()).filter(Boolean),
        youtube_channel_keywords: youtubeKeywords.split(",").map((s) => s.trim()).filter(Boolean),
        news_sources: [],
        reddit_communities: [],
        max_competitors_to_track: maxCompetitors,
      }),
    onSuccess: (segment) => {
      queryClient.setQueryData(["segment", brandId], segment);
    },
  });

  return (
    <main className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold">Data collection settings</h1>
        <p className="text-text-dim">Brand: {brandId}</p>
      </div>

      <section className="flex flex-col gap-3 rounded-lg border border-border p-4">
        <h2 className="text-lg font-medium">Data source credentials</h2>
        <p className="text-xs text-text-faint">
          Stored encrypted, per-brand -- a leaked key exposes only this brand&apos;s data collection.
        </p>

        {credentialsQuery.data && (
          <ul className="flex flex-col gap-1 text-sm text-text-dim">
            {credentialsQuery.data.map((c) => (
              <li key={c.source}>
                {c.source} — {c.rate_limit_per_hour}/hr
              </li>
            ))}
            {credentialsQuery.data.length === 0 && (
              <li className="text-text-faint">No credentials configured yet.</li>
            )}
          </ul>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <select
            className="rounded border border-border px-2 py-1 text-sm"
            value={source}
            onChange={(e) => setSource(e.target.value as DataSourceKind)}
          >
            {SOURCES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
          <input
            className="min-w-48 rounded border border-border px-2 py-1 text-sm"
            placeholder="API key"
            type="password"
            value={sourceApiKey}
            onChange={(e) => setSourceApiKey(e.target.value)}
          />
          <input
            className="w-24 rounded border border-border px-2 py-1 text-sm"
            type="number"
            value={rateLimit}
            onChange={(e) => setRateLimit(Number(e.target.value))}
          />
          <button
            type="button"
            className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            disabled={!sourceApiKey.trim() || saveCredential.isPending}
            onClick={() => saveCredential.mutate()}
          >
            {saveCredential.isPending ? "Saving…" : "Save credential"}
          </button>
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-lg border border-border p-4">
        <h2 className="text-lg font-medium">Market segment</h2>
        <p className="text-xs text-text-faint">
          Explicit whitelist for competitor discovery -- never open-ended crawling.
        </p>

        {segmentQuery.data && (
          <p className="text-xs text-text-dim">
            Current: {segmentQuery.data.segment_name} ({segmentQuery.data.website_urls.length} sites,{" "}
            {segmentQuery.data.max_competitors_to_track} max competitors)
          </p>
        )}

        <input
          className="rounded border border-border px-2 py-1 text-sm"
          placeholder="Segment name (e.g. fitness_wellness)"
          value={segmentName}
          onChange={(e) => setSegmentName(e.target.value)}
        />
        <input
          className="rounded border border-border px-2 py-1 text-sm"
          placeholder="Website URLs, comma-separated"
          value={websiteUrls}
          onChange={(e) => setWebsiteUrls(e.target.value)}
        />
        <input
          className="rounded border border-border px-2 py-1 text-sm"
          placeholder="YouTube channel keywords, comma-separated"
          value={youtubeKeywords}
          onChange={(e) => setYoutubeKeywords(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          Max competitors to track
          <input
            className="w-20 rounded border border-border px-2 py-1 text-sm"
            type="number"
            value={maxCompetitors}
            onChange={(e) => setMaxCompetitors(Number(e.target.value))}
          />
        </label>
        <button
          type="button"
          className="w-fit rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          disabled={!segmentName.trim() || saveSegment.isPending}
          onClick={() => saveSegment.mutate()}
        >
          {saveSegment.isPending ? "Saving…" : "Save segment"}
        </button>
      </section>
    </main>
  );
}
