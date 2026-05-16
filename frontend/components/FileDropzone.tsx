"use client";

import { ChangeEvent, DragEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import type { UploadResponse } from "@/lib/types";

const ACCEPTED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png", ".xlsx", ".xls", ".csv"];
const MAX_MB = 75;
const MAX_BYTES = MAX_MB * 1024 * 1024;

function validateFile(file: File): string | null {
  const dotExt = "." + (file.name.split(".").pop() ?? "").toLowerCase();
  if (!ACCEPTED_EXTENSIONS.includes(dotExt)) {
    return `"${dotExt || "(no extension)"}" is not supported. Accepted: ${ACCEPTED_EXTENSIONS.join(", ")}`;
  }
  if (file.size > MAX_BYTES) {
    return `File is ${(file.size / 1024 / 1024).toFixed(1)} MB — over the ${MAX_MB} MB limit.`;
  }
  if (file.size === 0) {
    return "The file appears to be empty.";
  }
  return null;
}

export function FileDropzone() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selected, setSelected] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);

  const pick = (file: File) => {
    setError(null);
    const err = validateFile(file);
    if (err) {
      setError(err);
      setSelected(null);
      return;
    }
    setSelected(file);
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) pick(file);
  };

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) pick(file);
    e.target.value = "";
  };

  const handleUpload = async () => {
    if (!selected || uploading) return;
    setUploading(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", selected);
      const res = await apiFetch<UploadResponse>("/api/sessions/upload", {
        method: "POST",
        body: form,
      });
      router.push(`/workspace/${res.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed. Please try again.");
      setUploading(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Select file — click or drag and drop"
        onClick={() => !uploading && inputRef.current?.click()}
        onKeyDown={(e) => e.key === "Enter" && !uploading && inputRef.current?.click()}
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        className={[
          "flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-12",
          "cursor-pointer transition-colors duration-150 select-none outline-none",
          "focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          isDragging
            ? "border-zinc-400 bg-zinc-50 dark:border-zinc-500 dark:bg-zinc-900"
            : "border-zinc-300 hover:border-zinc-400 dark:border-zinc-700 dark:hover:border-zinc-500",
          selected ? "bg-zinc-50 dark:bg-zinc-900/40" : "",
        ].join(" ")}
      >
        {/* Cloud-upload icon */}
        <svg
          aria-hidden="true"
          className={`w-10 h-10 ${selected ? "text-zinc-400" : "text-zinc-300 dark:text-zinc-600"}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>

        {selected ? (
          <div className="text-center">
            <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300 truncate max-w-xs">
              {selected.name}
            </p>
            <p className="text-xs text-zinc-400 mt-0.5">
              {(selected.size / 1024 / 1024).toFixed(2)} MB &nbsp;·&nbsp; click to change
            </p>
          </div>
        ) : (
          <div className="text-center">
            <p className="text-sm text-zinc-600 dark:text-zinc-400">
              Drop your file here, or{" "}
              <span className="font-medium underline underline-offset-2">click to browse</span>
            </p>
            <p className="text-xs text-zinc-400 mt-1">Max {MAX_MB} MB</p>
          </div>
        )}
      </div>

      {/* Accepted file types */}
      <div className="flex flex-wrap gap-1.5 justify-center">
        {ACCEPTED_EXTENSIONS.map((ext) => (
          <span
            key={ext}
            className="px-2 py-0.5 rounded text-xs font-mono bg-zinc-100 text-zinc-500 dark:bg-zinc-800 dark:text-zinc-400"
          >
            {ext}
          </span>
        ))}
      </div>

      {/* Error message */}
      {error && (
        <p role="alert" className="text-sm text-red-600 dark:text-red-400 text-center">
          {error}
        </p>
      )}

      {/* Upload button — only appears after valid file is selected */}
      {selected && !error && (
        <Button
          onClick={handleUpload}
          disabled={uploading}
          size="lg"
          className="w-full"
        >
          {uploading ? "Uploading…" : `Upload ${selected.name}`}
        </Button>
      )}

      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        accept={ACCEPTED_EXTENSIONS.join(",")}
        onChange={handleChange}
        aria-hidden="true"
      />
    </div>
  );
}
