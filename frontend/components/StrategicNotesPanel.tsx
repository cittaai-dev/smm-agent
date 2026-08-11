"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { addNote, listNotes } from "@/lib/api";
import { SECTION_LABELS, SECTION_ORDER } from "@/lib/sections";
import type { SectionId } from "@/lib/types";

// SOP-1 step 12: Team Lead annotate, ahead of approve/distribute. Notes are
// per-section commentary attached to the document -- not verified claims,
// not routed through Verify, deliberately outside the citation pipeline
// (this is the Team Lead's own voice, e.g. "double-check founding year").
export function StrategicNotesPanel({ documentId }: { documentId: string }) {
  const queryClient = useQueryClient();
  const queryKey = ["notes", documentId];

  const notes = useQuery({
    queryKey,
    queryFn: () => listNotes(documentId),
  });

  const [section, setSection] = useState<SectionId>(SECTION_ORDER[0]);
  const [text, setText] = useState("");
  const [author, setAuthor] = useState("");

  const submit = useMutation({
    mutationFn: () => addNote(documentId, section, text.trim(), author.trim()),
    onSuccess: () => {
      setText("");
      queryClient.invalidateQueries({ queryKey });
    },
  });

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-slate-200 p-4">
      <p className="text-sm font-medium text-slate-900">Team Lead notes</p>

      {notes.data && notes.data.length > 0 && (
        <ul className="flex flex-col gap-2">
          {notes.data.map((note) => (
            <li key={note.id} className="rounded-md bg-slate-50 p-3 text-sm">
              <div className="flex items-center justify-between text-xs text-slate-500">
                <span>{SECTION_LABELS[note.section as SectionId] ?? note.section}</span>
                <span>
                  {note.author} · {new Date(note.created_at).toLocaleString()}
                </span>
              </div>
              <p className="mt-1 text-slate-800">{note.text}</p>
            </li>
          ))}
        </ul>
      )}

      <div className="flex flex-col gap-2 border-t border-slate-100 pt-3">
        <div className="flex gap-2">
          <select
            aria-label="Section"
            className="rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            value={section}
            onChange={(e) => setSection(e.target.value as SectionId)}
          >
            {SECTION_ORDER.map((id) => (
              <option key={id} value={id}>
                {SECTION_LABELS[id]}
              </option>
            ))}
          </select>
          <input
            aria-label="Your name"
            className="w-40 rounded-md border border-slate-300 px-2 py-1.5 text-sm"
            placeholder="Your name"
            value={author}
            onChange={(e) => setAuthor(e.target.value)}
          />
        </div>
        <textarea
          aria-label="Note"
          className="min-h-16 rounded-md border border-slate-300 p-2 text-sm"
          placeholder="e.g. Double-check founding year against the About page."
          value={text}
          onChange={(e) => setText(e.target.value)}
        />
        <button
          type="button"
          className="w-fit rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          disabled={!text.trim() || !author.trim() || submit.isPending}
          onClick={() => submit.mutate()}
        >
          {submit.isPending ? "Adding…" : "Add note"}
        </button>
        {submit.isError && (
          <p className="text-sm text-red-700">{(submit.error as Error).message}</p>
        )}
      </div>
    </div>
  );
}
