"use client";

import { useMutation } from "@tanstack/react-query";
import { use } from "react";
import { uploadSource } from "@/lib/api";
import { BusinessGoalsForm } from "@/components/BusinessGoalsForm";
import { FileUploadZone } from "@/components/FileUploadZone";
import type { SourceKind } from "@/lib/types";

function UploadZone({
  brandId,
  sourceKind,
  label,
  accept,
}: {
  brandId: string;
  sourceKind: SourceKind;
  label: string;
  accept: string;
}) {
  const upload = useMutation({
    mutationFn: (file: File) => uploadSource(brandId, file, sourceKind),
  });
  return (
    <div className="flex flex-col gap-2">
      <FileUploadZone
        onUpload={(file) => upload.mutate(file)}
        disabled={upload.isPending}
        label={label}
        accept={accept}
      />
      {upload.isPending && <p className="text-sm text-text-dim">Uploading…</p>}
      {upload.isSuccess && (
        <p className="text-sm text-success">Queued for ingest: {upload.data.status}</p>
      )}
      {upload.isError && (
        <p className="text-sm text-danger">Upload failed: {(upload.error as Error).message}</p>
      )}
    </div>
  );
}

export default function OnboardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);

  return (
    <main className="flex flex-col gap-8">
      <div>
        <div className="mb-2.5 font-mono text-xs font-bold uppercase tracking-wide text-run">
          Step 1 / 6 · Brand Intake
        </div>
        <h1 className="text-[28px] font-bold">Onboard a Brand</h1>
        <p className="mt-2 max-w-xl text-text-dim">
          Every brand starts with the same intake: any material the brand already has gets uploaded
          here. Everything downstream — research, competitor analysis, the final document — builds on
          exactly what&apos;s captured in this step.
        </p>
        <p className="mt-2 text-sm text-text-faint">Brand: {brandId}</p>
      </div>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">Brand material</h2>
        <UploadZone
          brandId={brandId}
          sourceKind="brand_material"
          label="Brand deck, guidelines, or overview doc"
          accept=".pdf,.docx,.pptx,.png"
        />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">Analytics</h2>
        <UploadZone
          brandId={brandId}
          sourceKind="analytics"
          label="Follower/engagement export (CSV or Excel)"
          accept=".csv,.xlsx"
        />
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">
          Competitor material <span className="text-sm font-normal text-text-dim">(optional)</span>
        </h2>
        <UploadZone
          brandId={brandId}
          sourceKind="competitor_upload"
          label="Competitor deck or one-pager"
          accept=".pdf,.docx,.pptx,.png"
        />
      </section>

      <section>
        <BusinessGoalsForm brandId={brandId} />
      </section>
    </main>
  );
}
