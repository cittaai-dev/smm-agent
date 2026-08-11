"use client";

import { useMutation } from "@tanstack/react-query";
import Link from "next/link";
import { use } from "react";
import { uploadSource } from "@/lib/api";
import { FileUploadZone } from "@/components/FileUploadZone";

export default function UploadPage({ params }: { params: Promise<{ id: string }> }) {
  const { id: brandId } = use(params);

  const upload = useMutation({
    mutationFn: (file: File) => uploadSource(brandId, file),
  });

  return (
    <main className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Upload brand material</h1>
      <p className="text-slate-600">Brand: {brandId}</p>

      <FileUploadZone onUpload={(file) => upload.mutate(file)} disabled={upload.isPending} />

      {upload.isPending && <p className="text-sm text-slate-500">Uploading…</p>}
      {upload.isSuccess && (
        <p className="text-sm text-green-700">Queued for ingest: {upload.data.status}</p>
      )}
      {upload.isError && (
        <p className="text-sm text-red-700">Upload failed: {(upload.error as Error).message}</p>
      )}

      <Link
        href={`/brands/${encodeURIComponent(brandId)}/run`}
        className="mt-4 inline-block w-fit rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white"
      >
        Continue to run research
      </Link>
    </main>
  );
}
