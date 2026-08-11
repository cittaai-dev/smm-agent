"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
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
      {upload.isPending && <p className="text-sm text-slate-500">Uploading…</p>}
      {upload.isSuccess && (
        <p className="text-sm text-green-700">Queued for ingest: {upload.data.status}</p>
      )}
      {upload.isError && (
        <p className="text-sm text-red-700">Upload failed: {(upload.error as Error).message}</p>
      )}
    </div>
  );
}

export default function OnboardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);

  return (
    <main className="flex flex-col gap-8">
      <div>
        <h1 className="text-2xl font-semibold">Onboard brand material</h1>
        <p className="text-slate-600">Brand: {brandId}</p>
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
          Competitor material <span className="text-sm font-normal text-slate-500">(optional)</span>
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

      <Link
        href={`/brands/${encodeURIComponent(brandId)}/plan`}
        className="mt-2 inline-block w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        Continue to plan
      </Link>
    </main>
  );
}
