"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import type {
  ExtractionResponse,
  ProjectInfo,
  RecommendationsResponse,
  WindowItem,
} from "@/lib/types";
import { RecommendationSummary } from "@/components/RecommendationSummary";
import { MaterialSection } from "./MaterialSection";
import { ExportControls } from "./ExportControls";
import { QuoteMaterialSection } from "./QuoteMaterialSection";

type Tab = "takeoff" | "quote";

interface Props {
  sessionId: string;
  extractionReady: boolean;
}

export default function WorkspaceTabs({ sessionId, extractionReady }: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("takeoff");

  // ── Extraction state ──────────────────────────────────────────────────
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [projectInfo, setProjectInfo] = useState<ProjectInfo | null>(null);
  const [windowItems, setWindowItems] = useState<WindowItem[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // ── Quote state ───────────────────────────────────────────────────────
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState<string | null>(null);

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Load extraction when ready ────────────────────────────────────────
  useEffect(() => {
    if (!extractionReady) return;
    apiFetch<ExtractionResponse>(`/api/sessions/${sessionId}/extraction`)
      .then((data) => {
        setExtraction(data);
        setProjectInfo(data.project_info);
        setWindowItems(data.window_items);
      })
      .catch((err) =>
        setLoadError(err instanceof Error ? err.message : "Failed to load extraction.")
      );
  }, [sessionId, extractionReady]);

  // ── Autosave ──────────────────────────────────────────────────────────
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

  const handleAddWindow = (newItem: WindowItem) => {
    setWindowItems((prev) => [...prev, newItem]);
  };

  // ── Quote generation: flush → confirm → fetch ─────────────────────────
  const generateQuote = async (pi: ProjectInfo | null, wi: WindowItem[]) => {
    if (!extractionReady || quoteLoading) return;

    setQuoteLoading(true);
    setQuoteError(null);
    setRecommendations(null);

    // 1. Cancel pending debounce and flush immediately
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
      debounceRef.current = null;
    }
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
      setSaving(false);
      setQuoteLoading(false);
      return;
    }
    setSaving(false);

    // 2. Confirm (idempotent) + fetch recommendations
    try {
      await apiFetch(`/api/sessions/${sessionId}/confirm`, { method: "POST" });
      const data = await apiFetch<RecommendationsResponse>(
        `/api/sessions/${sessionId}/recommendations`
      );
      setRecommendations(data);
    } catch (err) {
      setQuoteError(
        err instanceof Error ? err.message : "Failed to generate recommendations."
      );
    } finally {
      setQuoteLoading(false);
    }
  };

  const handleQuoteTabClick = () => {
    setActiveTab("quote");
    generateQuote(projectInfo, windowItems);
  };

  return (
    <div className="flex flex-col h-full">

      {/* ── Tab bar ── */}
      <div className="shrink-0 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 px-6">
        <div className="flex items-center gap-0 -mb-px">
          <TabButton active={activeTab === "takeoff"} onClick={() => setActiveTab("takeoff")}>
            TAKE OFF
          </TabButton>
          <TabButton active={activeTab === "quote"} onClick={handleQuoteTabClick}>
            QUOTE
          </TabButton>

          {/* Save status */}
          <div className="ml-auto flex items-center gap-2 pb-2.5 text-xs">
            {saving && <span className="text-zinc-400">Saving…</span>}
            {!saving && saveError && (
              <span className="text-red-500 dark:text-red-400">{saveError}</span>
            )}
          </div>
        </div>
      </div>

      {/* ── Tab content ── */}
      <div className="flex-1 overflow-y-auto">

        {/* ── TAKE OFF tab ── */}
        {activeTab === "takeoff" && (
          <div className="px-6 py-6">
            {!extractionReady ? (
              <ProcessingPlaceholder />
            ) : loadError ? (
              <div className="text-center space-y-3 py-16">
                <p className="text-red-600 dark:text-red-400 text-sm">{loadError}</p>
                <a href="/upload" className="text-sm underline text-zinc-500">
                  ← Back to upload
                </a>
              </div>
            ) : !extraction ? (
              <LoadingSkeleton />
            ) : (
              <MaterialSection
                sessionId={sessionId}
                projectInfo={projectInfo}
                windowItems={windowItems}
                warnings={extraction.warnings}
                onProjectChange={handleProjectChange}
                onWindowsChange={handleWindowsChange}
                onAddWindow={handleAddWindow}
              />
            )}
          </div>
        )}

        {/* ── QUOTE tab ── */}
        {activeTab === "quote" && (
          <div className="px-6 py-6 space-y-6">
            {!extractionReady ? (
              <div className="text-center py-16 space-y-2">
                <p className="text-sm text-zinc-500 dark:text-zinc-400">
                  Waiting for extraction to complete…
                </p>
              </div>
            ) : quoteLoading ? (
              <QuoteLoadingState />
            ) : quoteError ? (
              <QuoteErrorState
                error={quoteError}
                onRetry={() => generateQuote(projectInfo, windowItems)}
              />
            ) : !recommendations ? null : (
              <>
                {/* Quote header */}
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
                      Supplier &amp; Pricing Recommendations
                    </h2>
                    <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
                      {recommendations.quote_table.length} quote
                      {recommendations.quote_table.length !== 1 ? "s" : ""} across{" "}
                      {new Set(recommendations.quote_table.map((r) => r.tag)).size} window tag
                      {new Set(recommendations.quote_table.map((r) => r.tag)).size !== 1 ? "s" : ""}
                    </p>
                  </div>
                  <button
                    onClick={() => generateQuote(projectInfo, windowItems)}
                    className="text-xs text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700 hover:border-zinc-300 dark:hover:border-zinc-600"
                  >
                    Regenerate
                  </button>
                </div>

                {/* Quote material sections (Windows/Doors/Walls) */}
                <QuoteMaterialSection rows={recommendations.quote_table} />

                {/* Summary */}
                {recommendations.natural_language_summary && (
                  <RecommendationSummary summary={recommendations.natural_language_summary} />
                )}

                {/* Export controls */}
                <ExportControls
                  sessionId={sessionId}
                  recommendations={recommendations}
                />
              </>
            )}
          </div>
        )}

      </div>
    </div>
  );
}

// ── Tab bar button ─────────────────────────────────────────────────────────────

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-3 text-xs font-semibold tracking-widest border-b-2 transition-colors whitespace-nowrap ${
        active
          ? "border-zinc-900 dark:border-zinc-100 text-zinc-900 dark:text-zinc-100"
          : "border-transparent text-zinc-400 dark:text-zinc-500 hover:text-zinc-600 dark:hover:text-zinc-300 hover:border-zinc-300 dark:hover:border-zinc-600"
      }`}
    >
      {children}
    </button>
  );
}

// ── TAKE OFF states ────────────────────────────────────────────────────────────

function ProcessingPlaceholder() {
  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-6">
        <div className="flex items-center gap-3 mb-5">
          <div className="w-4 h-4 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Extracting your data…
          </p>
        </div>
        <p className="text-xs text-zinc-400 dark:text-zinc-500 mb-5">
          The agent is analyzing your file. Watch the left panel for live progress.
        </p>
        <div className="space-y-2">
          {[100, 85, 70, 90, 60].map((w, i) => (
            <div
              key={i}
              className="h-3 rounded bg-zinc-100 dark:bg-zinc-800 animate-pulse"
              style={{ width: `${w}%` }}
            />
          ))}
        </div>
      </div>
      {["Doors", "Walls"].map((name) => (
        <div
          key={name}
          className="rounded-xl border border-zinc-200 dark:border-zinc-800 px-5 py-4 flex items-center gap-3 opacity-50"
        >
          <div className="h-3 w-16 rounded bg-zinc-200 dark:bg-zinc-700 animate-pulse" />
          <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-400">
            Coming Soon
          </span>
        </div>
      ))}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-6 space-y-3">
      {[100, 75, 90, 65, 80].map((w, i) => (
        <div
          key={i}
          className="h-3 rounded bg-zinc-100 dark:bg-zinc-800 animate-pulse"
          style={{ width: `${w}%` }}
        />
      ))}
    </div>
  );
}

// ── QUOTE states ───────────────────────────────────────────────────────────────

function QuoteLoadingState() {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-8">
      <div className="flex flex-col items-center gap-4">
        <div className="w-6 h-6 rounded-full border-2 border-zinc-400 border-t-zinc-800 dark:border-zinc-600 dark:border-t-zinc-100 animate-spin" />
        <div className="text-center space-y-1">
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Generating recommendations…
          </p>
          <p className="text-xs text-zinc-400 dark:text-zinc-500">
            Matching suppliers to your latest extraction data.
          </p>
        </div>
        <div className="w-full max-w-sm space-y-2 mt-2">
          {[100, 80, 90, 70].map((w, i) => (
            <div
              key={i}
              className="h-2.5 rounded bg-zinc-100 dark:bg-zinc-800 animate-pulse"
              style={{ width: `${w}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function QuoteErrorState({
  error,
  onRetry,
}: {
  error: string;
  onRetry: () => void;
}) {
  return (
    <div className="rounded-xl border border-red-200 dark:border-red-900/40 p-8 text-center space-y-3">
      <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
      <button
        onClick={onRetry}
        className="text-sm underline text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors"
      >
        Try again
      </button>
    </div>
  );
}

