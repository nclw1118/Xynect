"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { ExtractionResponse, ProjectInfo, WindowItem } from "@/lib/types";
import { ProjectInfoForm } from "@/components/ProjectInfoForm";
import { EditableWindowTable } from "@/components/EditableWindowTable";
import { ConfirmationModal } from "@/components/ConfirmationModal";
import { Button } from "@/components/ui/button";

export default function ReviewPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const router = useRouter();

  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [projectInfo, setProjectInfo] = useState<ProjectInfo | null>(null);
  const [windowItems, setWindowItems] = useState<WindowItem[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    apiFetch<ExtractionResponse>(`/api/sessions/${sessionId}/extraction`)
      .then((data) => {
        setExtraction(data);
        setProjectInfo(data.project_info);
        setWindowItems(data.window_items);
      })
      .catch((err) =>
        setLoadError(err instanceof Error ? err.message : "Failed to load extraction.")
      );
  }, [sessionId]);

  const schedulePatch = (pi: ProjectInfo | null, wi: WindowItem[]) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setSaving(true);
      setSaveError(null);
      try {
        await apiFetch(`/api/sessions/${sessionId}/extraction`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ project_info: pi ?? undefined, window_items: wi }),
        });
      } catch (err) {
        setSaveError(err instanceof Error ? err.message : "Save failed.");
      } finally {
        setSaving(false);
      }
    }, 600);
  };

  const handleProjectChange = (updated: Partial<ProjectInfo>) => {
    const next = { ...(projectInfo ?? ({} as ProjectInfo)), ...updated };
    setProjectInfo(next);
    schedulePatch(next, windowItems);
  };

  const handleWindowsChange = (updated: WindowItem[]) => {
    setWindowItems(updated);
    schedulePatch(projectInfo, updated);
  };

  if (loadError)
    return (
      <main className="flex min-h-screen items-center justify-center px-6 bg-white dark:bg-zinc-950">
        <div className="text-center space-y-3">
          <p className="text-red-600 dark:text-red-400 text-sm">{loadError}</p>
          <a href="/upload" className="text-sm underline text-zinc-500">← Back to upload</a>
        </div>
      </main>
    );

  if (!extraction)
    return (
      <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950">
        <p className="text-zinc-400 text-sm">Loading…</p>
      </main>
    );

  return (
    <>
      {showModal && (
        <ConfirmationModal
          sessionId={sessionId}
          onClose={() => setShowModal(false)}
          onConfirmed={(next) => router.push(next)}
        />
      )}

      <main className="min-h-screen bg-white dark:bg-zinc-950 px-4 py-10">
        <div className="max-w-6xl mx-auto space-y-8">

          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <p className="text-xs font-mono tracking-widest text-zinc-400 uppercase mb-1">Review</p>
              <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
                Review Extracted Window Data
              </h1>
            </div>
            <div className="flex gap-3 items-center">
              {saving && <span className="text-xs text-zinc-400">Saving…</span>}
              {saveError && <span className="text-xs text-red-500">{saveError}</span>}
              <a
                href="/upload"
                className="text-sm text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
              >
                ← Back to Upload
              </a>
              <Button size="lg" onClick={() => setShowModal(true)}>
                Confirm
              </Button>
            </div>
          </div>

          {extraction.warnings.length > 0 && (
            <div className="rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-900/20 dark:border-amber-700 p-4 space-y-1">
              {extraction.warnings.map((w, i) => (
                <p key={i} className="text-sm text-amber-700 dark:text-amber-300">{w}</p>
              ))}
            </div>
          )}

          <ProjectInfoForm info={projectInfo} onChange={handleProjectChange} />

          <div className="space-y-2">
            <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
              Window Schedule
              <span className="ml-2 font-normal text-zinc-400">
                ({windowItems.length} {windowItems.length === 1 ? "row" : "rows"})
              </span>
            </h2>
            <EditableWindowTable items={windowItems} onChange={handleWindowsChange} />
          </div>

        </div>
      </main>
    </>
  );
}
