"use client";

import { useQuery } from "@tanstack/react-query";
import { use } from "react";
import { ApiError, getClientView } from "@/lib/api";
import { SECTION_LABELS, SECTION_ORDER } from "@/lib/sections";

// No ClaimCard, no SectionStatusBadge, no ApproveButton import anywhere in
// this route -- the App Router's route-group split means there's no code
// path where an operator component accidentally renders on the client
// surface, unlike a conditionally-hidden prop a future edit could flip by
// mistake (step5_trust_boundary.md §11).
export default function ClientReportPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);

  const viewQuery = useQuery({
    queryKey: ["client-view", token],
    queryFn: () => getClientView(token),
    retry: false,
  });

  if (viewQuery.isLoading) {
    return <p className="text-text-dim">Loading…</p>;
  }

  if (viewQuery.isError) {
    const notFound = viewQuery.error instanceof ApiError && viewQuery.error.status === 404;
    return (
      <p className="text-danger">
        {notFound ? "This link has expired or is no longer valid." : "Could not load this report."}
      </p>
    );
  }

  const view = viewQuery.data!;

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-8 py-12">
      <h1 className="text-2xl font-bold">{view.brand_id} — Market Research</h1>

      {SECTION_ORDER.map((id) => {
        const claims = view.sections[id];
        if (!claims || claims.length === 0) return null;
        return (
          <section key={id}>
            <h2 className="mb-3 text-lg font-semibold">{SECTION_LABELS[id]}</h2>
            {claims.map((c, i) => (
              <p key={i} className="mb-2 text-sm text-text-dim">
                {c.text}
              </p>
            ))}
          </section>
        );
      })}

      {view.personas.length > 0 && (
        <section>
          <h2 className="mb-3 text-lg font-semibold">Audience Personas</h2>
          <div className="flex flex-col gap-3">
            {view.personas.map((p, i) => (
              <div key={i} className="rounded-lg border border-border p-3">
                <p className="text-sm font-medium">{p.name}</p>
                {p.pain_points.length > 0 && (
                  <p className="text-xs text-text-dim">Pain points: {p.pain_points.join(", ")}</p>
                )}
                {p.interests.length > 0 && (
                  <p className="text-xs text-text-dim">Interests: {p.interests.join(", ")}</p>
                )}
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
