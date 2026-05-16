"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import { ChevronDown } from "lucide-react";
import type { QuoteRow } from "@/lib/types";

interface Props {
  rows: QuoteRow[];
}

// ── Score badge ───────────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80
      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
      : pct >= 60
      ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
      : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold shrink-0 ${color}`}>
      {pct}%
    </span>
  );
}

// ── Risk note: keyword extraction + compact cell ───────────────────────────────

function extractRiskKeywords(note: string): string[] {
  if (!note) return [];
  const kws: string[] = [];

  if (/u[- ]?value/i.test(note) && /miss/i.test(note)) kws.push("Missing U-Value");
  else if (/u[- ]?value/i.test(note)) kws.push("U-Value");

  if (/\bshgc\b/i.test(note) && /miss/i.test(note)) kws.push("Missing SHGC");
  else if (/\bshgc\b/i.test(note)) kws.push("SHGC");

  if (/\bstate\b/i.test(note) && /miss/i.test(note)) kws.push("Missing State");

  if (/(dimension|width|height)\b/i.test(note) && /miss/i.test(note)) kws.push("Missing Dims");

  if (/quantit/i.test(note) && /miss/i.test(note)) kws.push("Missing Qty");
  else if (/quantit/i.test(note)) kws.push("Quantity");

  if (/glass|glaz/i.test(note) && /miss/i.test(note)) kws.push("Missing Glass");

  if (/opening type|op type/i.test(note) && /miss/i.test(note)) kws.push("Missing Type");

  if (/(frame|material)\b/i.test(note) && /miss/i.test(note)) kws.push("Missing Material");

  // Fallback: first 22 chars when nothing matched
  if (kws.length === 0) {
    kws.push(note.length > 22 ? note.slice(0, 22) + "…" : note);
  }

  return kws;
}

interface TooltipPos { x: number; y: number; }

function RiskCell({ note }: { note: string }) {
  const [pos, setPos] = useState<TooltipPos | null>(null);

  if (!note)
    return <span className="text-zinc-400 dark:text-zinc-600">—</span>;

  const keywords = extractRiskKeywords(note);

  return (
    <>
      <span
        onMouseEnter={(e) => {
          const r = e.currentTarget.getBoundingClientRect();
          setPos({ x: r.left, y: r.top });
        }}
        onMouseLeave={() => setPos(null)}
        className="cursor-help inline-flex flex-wrap gap-1 items-center"
      >
        {keywords.map((kw, i) => (
          <span
            key={i}
            className="inline-block px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400 border border-amber-200/70 dark:border-amber-800/40 whitespace-nowrap"
          >
            {kw}
          </span>
        ))}
        <span className="text-[10px] text-amber-500 dark:text-amber-600 ml-0.5 shrink-0">ⓘ</span>
      </span>

      {/* Portal tooltip — renders into document.body, escapes table overflow */}
      {pos !== null && createPortal(
        <div
          style={{
            position: "fixed",
            left: Math.min(pos.x, typeof window !== "undefined" ? window.innerWidth - 308 : pos.x),
            top: pos.y - 10,
            transform: "translateY(-100%)",
            zIndex: 9999,
          }}
          className="w-72 bg-zinc-900 dark:bg-zinc-50 text-zinc-100 dark:text-zinc-900 text-xs leading-relaxed rounded-xl px-3 py-2.5 shadow-2xl pointer-events-none"
        >
          {note}
          {/* Downward arrow */}
          <span
            className="absolute left-4 top-full w-0 h-0"
            style={{
              borderLeft: "5px solid transparent",
              borderRight: "5px solid transparent",
              borderTop: "5px solid",
              borderTopColor: "inherit",
            }}
          />
        </div>,
        document.body
      )}
    </>
  );
}

// ── Grouping helper ───────────────────────────────────────────────────────────

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

// ── Column definitions ────────────────────────────────────────────────────────

const SUP_COLS = [
  { label: "Rank",         w: "w-12" },
  { label: "Supplier",     w: "w-52" },
  { label: "Unit Price",   w: "w-24" },
  { label: "Qty",          w: "w-14" },
  { label: "Est. Total",   w: "w-28" },
  { label: "Lead Time",    w: "w-24" },
  { label: "Match Score",  w: "w-24" },
  { label: "Match Reason", w: "w-56" },
  { label: "Risk Notes",   w: "w-44" },
];

// ── Collapsible tag card ──────────────────────────────────────────────────────

function TagCard({ tag, suppliers }: { tag: string; suppliers: QuoteRow[] }) {
  const [isOpen, setIsOpen] = useState(false);
  const top = suppliers[0];

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
      {/* Clickable header — always visible */}
      <button
        type="button"
        onClick={() => setIsOpen((o) => !o)}
        className="w-full flex items-center gap-3 px-4 py-3 bg-zinc-50 dark:bg-zinc-900 hover:bg-zinc-100 dark:hover:bg-zinc-900/80 transition-colors text-left"
      >
        {/* Tag name */}
        <span className="font-mono text-sm font-bold text-zinc-800 dark:text-zinc-100 shrink-0">
          {tag}
        </span>

        {/* Recommended supplier */}
        <span className="text-xs text-zinc-500 dark:text-zinc-400 flex-1 truncate">
          {top.supplier}
          <span className="ml-1.5 text-emerald-600 dark:text-emerald-500 font-medium">
            Recommended
          </span>
        </span>

        {/* Est. total */}
        <span className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 shrink-0">
          ${top.estimated_total.toLocaleString(undefined, { maximumFractionDigits: 0 })}
        </span>

        {/* Match score */}
        <ScoreBadge score={top.match_score} />

        {/* Chevron */}
        <ChevronDown
          className={`w-4 h-4 text-zinc-400 dark:text-zinc-500 shrink-0 transition-transform duration-200 ${
            isOpen ? "rotate-180" : ""
          }`}
        />
      </button>

      {/* Expandable supplier table */}
      {isOpen && (
        <div className="border-t border-zinc-200 dark:border-zinc-800 overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-100 dark:border-zinc-800">
                {SUP_COLS.map((c) => (
                  <th
                    key={c.label}
                    className={`${c.w} px-3 py-2 text-left text-xs font-semibold text-zinc-400 dark:text-zinc-500 whitespace-nowrap`}
                  >
                    {c.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {suppliers.map((row, idx) => {
                const isTop = idx === 0;
                return (
                  <tr
                    key={idx}
                    className={`border-b border-zinc-100 dark:border-zinc-800 last:border-0 ${
                      isTop
                        ? "bg-emerald-50/40 dark:bg-emerald-900/10"
                        : "hover:bg-zinc-50/50 dark:hover:bg-zinc-900/30"
                    }`}
                  >
                    {/* Rank */}
                    <td className="w-12 px-3 py-2.5 whitespace-nowrap">
                      {isTop ? (
                        <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                          #1
                          <span className="hidden sm:inline font-normal text-emerald-600 dark:text-emerald-500">
                            Best
                          </span>
                        </span>
                      ) : (
                        <span className="text-xs text-zinc-400 dark:text-zinc-500">
                          #{idx + 1}
                        </span>
                      )}
                    </td>

                    {/* Supplier */}
                    <td className="w-52 px-3 py-2.5 whitespace-nowrap">
                      <span
                        className={`text-xs font-medium ${
                          isTop
                            ? "text-zinc-900 dark:text-zinc-100"
                            : "text-zinc-700 dark:text-zinc-300"
                        }`}
                      >
                        {row.supplier}
                      </span>
                      {isTop && (
                        <span className="ml-2 text-xs text-emerald-600 dark:text-emerald-500 font-normal">
                          Recommended
                        </span>
                      )}
                    </td>

                    {/* Unit Price */}
                    <td className="w-24 px-3 py-2.5 text-xs text-zinc-700 dark:text-zinc-300 whitespace-nowrap">
                      ${row.unit_price.toFixed(0)}
                    </td>

                    {/* Qty */}
                    <td className="w-14 px-3 py-2.5 text-xs text-zinc-700 dark:text-zinc-300 text-center">
                      {row.quantity}
                    </td>

                    {/* Est. Total */}
                    <td className="w-28 px-3 py-2.5 text-xs font-medium text-zinc-800 dark:text-zinc-200 whitespace-nowrap">
                      ${row.estimated_total.toFixed(0)}
                    </td>

                    {/* Lead Time */}
                    <td className="w-24 px-3 py-2.5 text-xs text-zinc-500 dark:text-zinc-400 whitespace-nowrap">
                      {row.lead_time_days}d
                    </td>

                    {/* Match Score */}
                    <td className="w-24 px-3 py-2.5 whitespace-nowrap">
                      <ScoreBadge score={row.match_score} />
                    </td>

                    {/* Match Reason */}
                    <td className="w-56 px-3 py-2.5 text-xs text-zinc-500 dark:text-zinc-400">
                      {row.match_reason}
                    </td>

                    {/* Risk Notes — compact keyword pills */}
                    <td className="w-44 px-3 py-2.5">
                      <RiskCell note={row.risk_notes} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Public component ──────────────────────────────────────────────────────────

export function QuoteTable({ rows }: Props) {
  if (rows.length === 0)
    return (
      <p className="text-sm text-zinc-400 py-8 text-center">
        No recommendations available.
      </p>
    );

  const groups = groupByTag(rows);

  return (
    <div className="space-y-3">
      {Array.from(groups.entries()).map(([tag, suppliers]) => (
        <TagCard key={tag} tag={tag} suppliers={suppliers} />
      ))}
    </div>
  );
}
