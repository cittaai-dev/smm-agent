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
// whitelist. Placeholder auth (api-key input), same pattern as core-kb's
// page -- a real login flow is still out of scope here.
export default function BrandSettingsPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");

  const credentialsQuery = useQuery({
    queryKey: ["credentials", brandId, apiKey],
    queryFn: () => listDataSourceCredentials(apiKey, brandId),
    enabled: apiKey.length > 0,
  });

  const segmentQuery = useQuery({
    queryKey: ["segment", brandId, apiKey],
    queryFn: () => getMarketSegment(apiKey, brandId),
    enabled: apiKey.length > 0,
  });

  const [source, setSource] = useState<DataSourceKind>("newsapi");
  const [sourceApiKey, setSourceApiKey] = useState("");
  const [rateLimit, setRateLimit] = useState(60);

  const saveCredential = useMutation({
    mutationFn: () => saveDataSourceCredential(apiKey, brandId, source, sourceApiKey, rateLimit),
    onSuccess: () => {
      setSourceApiKey("");
      queryClient.invalidateQueries({ queryKey: ["credentials", brandId, apiKey] });
    },
  });

  const [segmentName, setSegmentName] = useState("");
  const [websiteUrls, setWebsiteUrls] = useState("");
  const [youtubeKeywords, setYoutubeKeywords] = useState("");
  const [maxCompetitors, setMaxCompetitors] = useState(10);

  const saveSegment = useMutation({
    mutationFn: () =>
      setMarketSegment(apiKey, brandId, {
        segment_name: segmentName,
        website_urls: websiteUrls.split(",").map((s) => s.trim()).filter(Boolean),
        youtube_channel_keywords: youtubeKeywords.split(",").map((s) => s.trim()).filter(Boolean),
        news_sources: [],
        reddit_communities: [],
        max_competitors_to_track: maxCompetitors,
      }),
    onSuccess: (segment) => {
      queryClient.setQueryData(["segment", brandId, apiKey], segment);
    },
  });

  return (
    <main className="flex flex-col gap-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Data collection settings</h1>
          <p className="text-slate-600">Brand: {brandId}</p>
        </div>
        <input
          className="rounded border border-slate-300 px-2 py-1 text-sm"
          placeholder="api-key"
          value={apiKey}
          onChange={(e) => setApiKey(e.target.value)}
        />
      </div>

      <section className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4">
        <h2 className="text-lg font-medium">Data source credentials</h2>
        <p className="text-xs text-slate-400">
          Stored encrypted, per-brand -- a leaked key exposes only this brand&apos;s data collection.
        </p>

        {credentialsQuery.data && (
          <ul className="flex flex-col gap-1 text-sm text-slate-700">
            {credentialsQuery.data.map((c) => (
              <li key={c.source}>
                {c.source} — {c.rate_limit_per_hour}/hr
              </li>
            ))}
            {credentialsQuery.data.length === 0 && (
              <li className="text-slate-400">No credentials configured yet.</li>
            )}
          </ul>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <select
            className="rounded border border-slate-300 px-2 py-1 text-sm"
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
            className="min-w-48 rounded border border-slate-300 px-2 py-1 text-sm"
            placeholder="API key"
            type="password"
            value={sourceApiKey}
            onChange={(e) => setSourceApiKey(e.target.value)}
          />
          <input
            className="w-24 rounded border border-slate-300 px-2 py-1 text-sm"
            type="number"
            value={rateLimit}
            onChange={(e) => setRateLimit(Number(e.target.value))}
          />
          <button
            type="button"
            className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
            disabled={!apiKey || !sourceApiKey.trim() || saveCredential.isPending}
            onClick={() => saveCredential.mutate()}
          >
            {saveCredential.isPending ? "Saving…" : "Save credential"}
          </button>
        </div>
      </section>

      <section className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4">
        <h2 className="text-lg font-medium">Market segment</h2>
        <p className="text-xs text-slate-400">
          Explicit whitelist for competitor discovery -- never open-ended crawling.
        </p>

        {segmentQuery.data && (
          <p className="text-xs text-slate-500">
            Current: {segmentQuery.data.segment_name} ({segmentQuery.data.website_urls.length} sites,{" "}
            {segmentQuery.data.max_competitors_to_track} max competitors)
          </p>
        )}

        <input
          className="rounded border border-slate-300 px-2 py-1 text-sm"
          placeholder="Segment name (e.g. fitness_wellness)"
          value={segmentName}
          onChange={(e) => setSegmentName(e.target.value)}
        />
        <input
          className="rounded border border-slate-300 px-2 py-1 text-sm"
          placeholder="Website URLs, comma-separated"
          value={websiteUrls}
          onChange={(e) => setWebsiteUrls(e.target.value)}
        />
        <input
          className="rounded border border-slate-300 px-2 py-1 text-sm"
          placeholder="YouTube channel keywords, comma-separated"
          value={youtubeKeywords}
          onChange={(e) => setYoutubeKeywords(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm">
          Max competitors to track
          <input
            className="w-20 rounded border border-slate-300 px-2 py-1 text-sm"
            type="number"
            value={maxCompetitors}
            onChange={(e) => setMaxCompetitors(Number(e.target.value))}
          />
        </label>
        <button
          type="button"
          className="w-fit rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-40"
          disabled={!apiKey || !segmentName.trim() || saveSegment.isPending}
          onClick={() => saveSegment.mutate()}
        >
          {saveSegment.isPending ? "Saving…" : "Save segment"}
        </button>
      </section>
    </main>
  );
}
