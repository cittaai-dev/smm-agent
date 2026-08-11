"use client";

import { useRef, useState } from "react";

export function FileUploadZone({
  onUpload,
  disabled,
}: {
  onUpload: (file: File) => void;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [lastFileName, setLastFileName] = useState<string | null>(null);

  function handleFiles(files: FileList | null) {
    const file = files?.[0];
    if (!file) return;
    setLastFileName(file.name);
    onUpload(file);
  }

  return (
    <div
      className="flex flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-slate-300 p-10 text-center"
      onDragOver={(e) => e.preventDefault()}
      onDrop={(e) => {
        e.preventDefault();
        handleFiles(e.dataTransfer.files);
      }}
    >
      <p className="text-slate-600">Drag a brand document here, or</p>
      <button
        type="button"
        className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        disabled={disabled}
        onClick={() => inputRef.current?.click()}
      >
        Choose file
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {lastFileName && <p className="text-xs text-slate-500">Last selected: {lastFileName}</p>}
    </div>
  );
}
