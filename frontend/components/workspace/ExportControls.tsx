"use client";

import type { QuoteRow, RecommendationsResponse } from "@/lib/types";

interface Props {
  sessionId: string;
  recommendations: RecommendationsResponse;
}

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

function cell(value: string): string {
  return `"${value.replace(/"/g, '""')}"`;
}

export function ExportControls({ sessionId, recommendations }: Props) {
  const handleExportCSV = () => {
    const headers = [
      "Tag",
      "Rank",
      "Supplier",
      "Unit Price",
      "Quantity",
      "Estimated Total",
      "Lead Time (days)",
      "Match Score",
      "Match Reason",
      "Risk Notes",
    ];

    const groups = groupByTag(recommendations.quote_table);
    const dataRows: string[][] = [];

    for (const [tag, suppliers] of groups) {
      suppliers.forEach((row, idx) => {
        dataRows.push([
          tag,
          `#${idx + 1}`,
          row.supplier,
          `$${row.unit_price.toFixed(0)}`,
          String(row.quantity),
          `$${row.estimated_total.toFixed(0)}`,
          String(row.lead_time_days),
          `${Math.round(row.match_score * 100)}%`,
          row.match_reason,
          row.risk_notes || "",
        ]);
      });
    }

    const csv = [headers, ...dataRows]
      .map((row) => row.map(cell).join(","))
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `xynect_recommendations_${sessionId}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleExportPDF = () => {
    window.open(`/workspace/${sessionId}/print`, "_blank");
  };

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-5">
      <h3 className="text-xs font-semibold text-zinc-600 dark:text-zinc-400 uppercase tracking-wide mb-4">
        Export
      </h3>
      <div className="flex flex-wrap gap-3">
        <button
          onClick={handleExportCSV}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/60 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
        >
          <CsvIcon />
          Export CSV
        </button>
        <button
          onClick={handleExportPDF}
          className="flex items-center gap-2 px-4 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/60 text-sm font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-50 dark:hover:bg-zinc-800 hover:border-zinc-300 dark:hover:border-zinc-600 transition-colors"
        >
          <PdfIcon />
          Export PDF Report
        </button>
      </div>
      <p className="text-[10px] text-zinc-400 dark:text-zinc-500 mt-3">
        PDF Report opens a printable view — use your browser's Save as PDF option.
      </p>
    </div>
  );
}

function CsvIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function PdfIcon() {
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="M9 13h.01" />
      <path d="M9 17h6" />
      <path d="M9 9h6" />
    </svg>
  );
}
