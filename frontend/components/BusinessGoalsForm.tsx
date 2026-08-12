"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { getTeamInput, submitTeamInput } from "@/lib/api";

const SECTION_ID = "business_goals";

export function BusinessGoalsForm({ brandId }: { brandId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["team-input", brandId, SECTION_ID];
  const existing = useQuery({
    queryKey,
    queryFn: () => getTeamInput(brandId, SECTION_ID),
  });
  const [text, setText] = useState("");

  useEffect(() => {
    if (existing.data) setText(existing.data.text);
  }, [existing.data]);

  const submit = useMutation({
    mutationFn: () => submitTeamInput(brandId, SECTION_ID, text.trim()),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey });
    },
  });

  return (
    <div className="flex flex-col gap-2">
      <label className="font-medium text-text" htmlFor="business-goals">
        Business goals
      </label>
      <p className="text-sm text-text-dim">
        Not inferred from uploaded material — this section is Team-Lead-authored input.
      </p>
      <textarea
        id="business-goals"
        className="min-h-24 rounded-md border border-border p-3"
        placeholder="e.g. Grow DTC revenue 20% YoY, expand into Canada by Q4."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button
        type="button"
        className="w-fit rounded-md bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        disabled={!text.trim() || submit.isPending}
        onClick={() => submit.mutate()}
      >
        {submit.isPending ? "Saving…" : "Save"}
      </button>
      {submit.isSuccess && <p className="text-sm text-success">Saved.</p>}
      {submit.isError && <p className="text-sm text-danger">{(submit.error as Error).message}</p>}
    </div>
  );
}
