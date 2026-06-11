"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { ExtractionResponse, RecommendationsResponse, QuoteRow } from "@/lib/types";

// ── Group rows by tag ─────────────────────────────────────────────────────────

function groupByTag(rows: QuoteRow[]): Map<string, QuoteRow[]> {
  const map = new Map<string, QuoteRow[]>();
  for (const row of rows) {
    if (!map.has(row.tag)) map.set(row.tag, []);
    map.get(row.tag)!.push(row);
  }
  for (const [tag, group] of map) {
    map.set(tag, [...group].sort((a, b) => b.match_score - a.match_score));
  }
  return map;
}

// ── Print-friendly score badge ────────────────────────────────────────────────

function ScorePill({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return <span className="font-semibold">{pct}%</span>;
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function PrintPage() {
  const { sessionId } = useParams<{ sessionId: string }>();

  const [recs, setRecs] = useState<RecommendationsResponse | null>(null);
  const [extraction, setExtraction] = useState<ExtractionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      apiFetch<RecommendationsResponse>(`/api/sessions/${sessionId}/recommendations`),
      apiFetch<ExtractionResponse>(`/api/sessions/${sessionId}/extraction`).catch(() => null),
    ])
      .then(([recData, extData]) => {
        setRecs(recData);
        setExtraction(extData);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to load report data.");
      });
  }, [sessionId]);

  // Auto-print once data is loaded
  useEffect(() => {
    if (recs) {
      const timer = setTimeout(() => window.print(), 600);
      return () => clearTimeout(timer);
    }
  }, [recs]);

  const timestamp = new Date().toLocaleString();
  const projectName = extraction?.project_info?.project_name;
  const siteAddress = extraction?.project_info?.site_address;
  const state = extraction?.project_info?.state;

  if (error) {
    return (
      <main className="min-h-screen flex items-center justify-center p-8">
        <div className="text-center space-y-4">
          <p className="text-red-600 text-sm">{error}</p>
          <p className="text-zinc-500 text-xs">
            Make sure recommendations have been generated in the QUOTE tab first, then reopen this page.
          </p>
        </div>
      </main>
    );
  }

  if (!recs) {
    return (
      <main className="min-h-screen flex items-center justify-center p-8">
        <p className="text-zinc-400 text-sm animate-pulse">Preparing report…</p>
      </main>
    );
  }

  const groups = groupByTag(recs.quote_table);
  const summaryParagraphs = recs.natural_language_summary.split("\n\n").filter(Boolean);

  return (
    <div className="bg-white min-h-screen">

      {/* ── Screen-only print bar (hidden when printing) ── */}
      <div className="print:hidden sticky top-0 z-10 bg-white border-b border-zinc-200 px-6 py-3 flex items-center justify-end">
        <button
          onClick={() => window.print()}
          className="px-4 py-1.5 rounded-lg bg-zinc-900 text-white text-sm font-medium hover:bg-zinc-700 transition-colors"
        >
          Print / Save as PDF
        </button>
      </div>

      {/* ── Report content ── */}
      <div className="max-w-5xl mx-auto px-8 py-10 space-y-8">

        {/* Report header */}
        <div className="border-b border-zinc-200 pb-6">
          <h1 className="text-2xl font-bold text-zinc-900 tracking-tight">
            Xynect — Supplier Recommendations Report
          </h1>
          <p className="text-sm text-zinc-500 mt-1">Generated {timestamp}</p>
          {(projectName || siteAddress || state) && (
            <div className="mt-3 space-y-0.5">
              {projectName && (
                <p className="text-sm text-zinc-700">
                  <span className="font-medium">Project:</span> {projectName}
                </p>
              )}
              {siteAddress && (
                <p className="text-sm text-zinc-700">
                  <span className="font-medium">Address:</span> {siteAddress}
                  {state ? `, ${state}` : ""}
                </p>
              )}
            </div>
          )}
          <p className="text-xs text-zinc-400 mt-2 font-mono">Session: {sessionId}</p>
        </div>

        {/* Recommendations by tag */}
        <div className="space-y-8">
          <h2 className="text-base font-semibold text-zinc-800">
            Recommendations by Tag
          </h2>

          {Array.from(groups.entries()).map(([tag, suppliers]) => {
            const top = suppliers[0];
            return (
              <div key={tag} className="space-y-2">
                {/* Tag header */}
                <div className="flex items-center gap-3 pb-1 border-b border-zinc-200">
                  <span className="font-mono text-sm font-bold text-zinc-800">{tag}</span>
                  <span className="text-xs text-zinc-500">
                    Recommended: {top.supplier} — <ScorePill score={top.match_score} />
                  </span>
                </div>

                {/* Supplier table */}
                <table className="w-full text-xs border-collapse">
                  <thead>
                    <tr className="bg-zinc-50 text-zinc-500">
                      {["Rank", "Supplier", "Unit Price", "Qty", "Est. Total", "Lead Time", "Score", "Match Reason", "Risk Notes"].map((h) => (
                        <th key={h} className="text-left px-2 py-1.5 font-semibold whitespace-nowrap border border-zinc-200">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {suppliers.map((row, idx) => (
                      <tr key={idx} className={idx === 0 ? "bg-emerald-50" : "bg-white"}>
                        <td className="px-2 py-1.5 border border-zinc-200 font-semibold text-zinc-700">
                          #{idx + 1}{idx === 0 ? " ★" : ""}
                        </td>
                        <td className="px-2 py-1.5 border border-zinc-200 font-medium text-zinc-800">
                          {row.supplier}
                        </td>
                        <td className="px-2 py-1.5 border border-zinc-200 text-zinc-700">
                          ${row.unit_price.toFixed(0)}
                        </td>
                        <td className="px-2 py-1.5 border border-zinc-200 text-zinc-700 text-center">
                          {row.quantity}
                        </td>
                        <td className="px-2 py-1.5 border border-zinc-200 font-semibold text-zinc-800">
                          ${row.estimated_total.toFixed(0)}
                        </td>
                        <td className="px-2 py-1.5 border border-zinc-200 text-zinc-600">
                          {row.lead_time_days}d
                        </td>
                        <td className="px-2 py-1.5 border border-zinc-200">
                          <ScorePill score={row.match_score} />
                        </td>
                        <td className="px-2 py-1.5 border border-zinc-200 text-zinc-500">
                          {row.match_reason}
                        </td>
                        <td className="px-2 py-1.5 border border-zinc-200 text-amber-700">
                          {row.risk_notes || "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          })}
        </div>

        {/* Summary */}
        {summaryParagraphs.length > 0 && (
          <div className="space-y-3 border-t border-zinc-200 pt-6">
            <h2 className="text-base font-semibold text-zinc-800">Recommendation Summary</h2>
            {summaryParagraphs.map((p, i) => (
              <p key={i} className="text-sm text-zinc-600 leading-relaxed">
                {p}
              </p>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="border-t border-zinc-200 pt-4 text-xs text-zinc-400">
          Generated by Xynect AI — construction material supply chain platform. For informational purposes only.
        </div>

      </div>
    </div>
  );
}
