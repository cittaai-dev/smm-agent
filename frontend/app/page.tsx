"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export default function Home() {
  const [brandId, setBrandId] = useState("");
  const router = useRouter();

  function goToUpload(e: React.FormEvent) {
    e.preventDefault();
    const id = brandId.trim();
    if (!id) return;
    router.push(`/brands/${encodeURIComponent(id)}/onboard`);
  }

  return (
    <main className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Start a brand's Market Research</h1>
      <p className="text-slate-600">
        Enter a brand id to onboard material and run the full SOP-01 Market Research document.
      </p>
      <form onSubmit={goToUpload} className="flex gap-2">
        <input
          className="flex-1 rounded-md border border-slate-300 px-3 py-2"
          placeholder="brand id, e.g. acme-roasters"
          value={brandId}
          onChange={(e) => setBrandId(e.target.value)}
        />
        <button
          type="submit"
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
          disabled={!brandId.trim()}
        >
          Continue
        </button>
      </form>
    </main>
  );
}
