"use client";

import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { getDocument } from "@/lib/api";
import { DocumentSectionsReview } from "@/components/DocumentSectionsReview";

export default function SynthesizePage() {
  const searchParams = useSearchParams();
  const documentId = searchParams.get("documentId");

  const documentQuery = useQuery({
    queryKey: ["document", documentId],
    queryFn: () => getDocument(documentId as string),
    enabled: !!documentId,
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="mb-2.5 font-mono text-xs font-bold uppercase tracking-wide text-run">
          Step 5 / 6 · Synthesis
        </div>
        <h1 className="text-[28px] font-bold">Synthesize Findings</h1>
        <p className="mt-2 max-w-xl text-text-dim">
          Every claim is tagged with the source it came from. A claim that can&apos;t be traced back gets
          rejected and rewritten before the Team Lead ever sees it.
        </p>
      </div>

      {!documentId && (
        <p className="text-sm text-text-faint">
          Run research from Step 2 first — this step reviews that run&apos;s claims.
        </p>
      )}
      {documentQuery.isLoading && <p className="text-text-dim">Loading…</p>}
      {documentQuery.isError && (
        <p className="text-danger">Could not load this run&apos;s findings.</p>
      )}
      {documentQuery.data && <DocumentSectionsReview document={documentQuery.data} />}
    </div>
  );
}
