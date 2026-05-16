"use client";

import { useState } from "react";
import { AppWindow, DoorOpen, Layers, ChevronDown } from "lucide-react";
import type { QuoteRow } from "@/lib/types";
import { QuoteTable } from "@/components/QuoteTable";

interface Props {
  rows: QuoteRow[];
}

export function QuoteMaterialSection({ rows }: Props) {
  const [windowsOpen, setWindowsOpen] = useState(true);
  const [doorsOpen, setDoorsOpen] = useState(false);
  const [wallsOpen, setWallsOpen] = useState(false);

  const tagCount = new Set(rows.map((r) => r.tag)).size;

  return (
    <div className="space-y-3">

      {/* ── Windows — enabled ── */}
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
          {!windowsOpen && tagCount > 0 && (
            <span className="text-[10px] text-zinc-400 dark:text-zinc-500 mr-1">
              {tagCount} {tagCount === 1 ? "tag" : "tags"}
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
          <div className="border-t border-zinc-200 dark:border-zinc-800 px-5 py-5">
            {rows.length === 0 ? (
              <p className="text-sm text-zinc-400 dark:text-zinc-500 text-center py-4">
                No window quotes available. Make sure the window schedule has valid tags.
              </p>
            ) : (
              <QuoteTable rows={rows} />
            )}
          </div>
        )}
      </section>

      {/* ── Doors — coming soon ── */}
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
              Door quotes are coming soon.
            </p>
          </div>
        )}
      </section>

      {/* ── Walls — coming soon ── */}
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
              Wall quotes are coming soon.
            </p>
          </div>
        )}
      </section>

    </div>
  );
}
