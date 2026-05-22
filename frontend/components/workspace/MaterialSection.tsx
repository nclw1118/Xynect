"use client";

import { useState } from "react";
import { AppWindow, DoorOpen, Layers, Plus, ChevronDown } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { WindowItem } from "@/lib/types";
import { EditableWindowTable } from "@/components/EditableWindowTable";

interface Props {
  sessionId: string;
  windowItems: WindowItem[];
  warnings: string[];
  onWindowsChange: (updated: WindowItem[]) => void;
  onAddWindow: (newItem: WindowItem) => void;
}

export function MaterialSection({
  sessionId,
  windowItems,
  warnings,
  onWindowsChange,
  onAddWindow,
}: Props) {
  const [windowsOpen, setWindowsOpen] = useState(true);
  const [doorsOpen, setDoorsOpen] = useState(false);
  const [wallsOpen, setWallsOpen] = useState(false);

  const [addingWindow, setAddingWindow] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const handleAddWindow = async () => {
    setAddingWindow(true);
    setAddError(null);
    try {
      const newItem = await apiFetch<WindowItem>(
        `/api/sessions/${sessionId}/windows`,
        { method: "POST" }
      );
      onAddWindow(newItem);
    } catch (err) {
      setAddError(err instanceof Error ? err.message : "Failed to add window.");
    } finally {
      setAddingWindow(false);
    }
  };

  return (
    <div className="space-y-3">

      {/* ── Windows ── */}
      <section className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <button
          type="button"
          onClick={() => setWindowsOpen((o) => !o)}
          className="w-full flex items-center gap-3 px-5 py-4 bg-zinc-50 dark:bg-zinc-900/60 hover:bg-zinc-100 dark:hover:bg-zinc-900/80 transition-colors text-left"
        >
          <AppWindow className="w-4 h-4 text-zinc-600 dark:text-zinc-400 shrink-0" />
          <span className="text-sm font-semibold text-zinc-800 dark:text-zinc-100 flex-1">
            Windows
          </span>
          {!windowsOpen && windowItems.length > 0 && (
            <span className="text-[10px] text-zinc-400 dark:text-zinc-500 mr-1">
              {windowItems.length} {windowItems.length === 1 ? "row" : "rows"}
            </span>
          )}
          <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400">
            Active
          </span>
          <ChevronDown
            className={`w-4 h-4 text-zinc-400 dark:text-zinc-500 shrink-0 transition-transform duration-200 ${
              windowsOpen ? "rotate-180" : ""
            }`}
          />
        </button>

        {windowsOpen && (
          <div className="border-t border-zinc-200 dark:border-zinc-800 px-5 py-5 space-y-5">

            {/* Warnings */}
            {warnings.length > 0 && (
              <div className="rounded-lg bg-amber-50 border border-amber-200 dark:bg-amber-900/20 dark:border-amber-700 px-4 py-3 space-y-1">
                {warnings.map((w, i) => (
                  <p key={i} className="text-xs text-amber-700 dark:text-amber-300">
                    {w}
                  </p>
                ))}
              </div>
            )}

            {/* Window schedule + Add Window */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wide">
                  Window Schedule
                  <span className="ml-2 font-normal normal-case text-zinc-400">
                    ({windowItems.length} {windowItems.length === 1 ? "row" : "rows"})
                  </span>
                </h3>
                <div className="flex items-center gap-2">
                  {addError && (
                    <span className="text-xs text-red-500 dark:text-red-400">{addError}</span>
                  )}
                  <button
                    onClick={handleAddWindow}
                    disabled={addingWindow}
                    className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/60 text-xs font-medium text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <Plus className="w-3 h-3" />
                    {addingWindow ? "Adding…" : "Add Window"}
                  </button>
                </div>
              </div>

              <EditableWindowTable items={windowItems} onChange={onWindowsChange} />
            </div>

          </div>
        )}
      </section>

      {/* ── Doors ── */}
      <section className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <button
          type="button"
          onClick={() => setDoorsOpen((o) => !o)}
          className="w-full flex items-center gap-3 px-5 py-4 bg-zinc-50 dark:bg-zinc-900/60 hover:bg-zinc-100/60 dark:hover:bg-zinc-900/80 transition-colors text-left"
        >
          <DoorOpen className="w-4 h-4 text-zinc-400 dark:text-zinc-600 shrink-0" />
          <span className="text-sm font-semibold text-zinc-400 dark:text-zinc-600 flex-1">
            Doors
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-500">
            Coming Soon
          </span>
          <ChevronDown
            className={`w-4 h-4 text-zinc-300 dark:text-zinc-600 shrink-0 transition-transform duration-200 ${
              doorsOpen ? "rotate-180" : ""
            }`}
          />
        </button>

        {doorsOpen && (
          <div className="border-t border-zinc-200 dark:border-zinc-800 px-5 py-6 text-center">
            <p className="text-sm text-zinc-400 dark:text-zinc-500">
              Door extraction is coming soon.
            </p>
          </div>
        )}
      </section>

      {/* ── Walls ── */}
      <section className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
        <button
          type="button"
          onClick={() => setWallsOpen((o) => !o)}
          className="w-full flex items-center gap-3 px-5 py-4 bg-zinc-50 dark:bg-zinc-900/60 hover:bg-zinc-100/60 dark:hover:bg-zinc-900/80 transition-colors text-left"
        >
          <Layers className="w-4 h-4 text-zinc-400 dark:text-zinc-600 shrink-0" />
          <span className="text-sm font-semibold text-zinc-400 dark:text-zinc-600 flex-1">
            Walls
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-400 dark:text-zinc-500">
            Coming Soon
          </span>
          <ChevronDown
            className={`w-4 h-4 text-zinc-300 dark:text-zinc-600 shrink-0 transition-transform duration-200 ${
              wallsOpen ? "rotate-180" : ""
            }`}
          />
        </button>

        {wallsOpen && (
          <div className="border-t border-zinc-200 dark:border-zinc-800 px-5 py-6 text-center">
            <p className="text-sm text-zinc-400 dark:text-zinc-500">
              Wall extraction is coming soon.
            </p>
          </div>
        )}
      </section>

    </div>
  );
}
