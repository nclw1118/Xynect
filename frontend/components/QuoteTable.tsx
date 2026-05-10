import type { QuoteRow } from "@/lib/types";

interface Props {
  rows: QuoteRow[];
}

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color =
    pct >= 80
      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400"
      : pct >= 60
      ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
      : "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";
  return (
    <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold ${color}`}>
      {pct}%
    </span>
  );
}

/** Group rows by tag, preserving the order tags first appear, sorted by match_score desc within each group. */
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

const SUP_COLS = [
  { label: "Rank",         w: "w-12" },
  { label: "Supplier",     w: "w-52" },
  { label: "Unit Price",   w: "w-24" },
  { label: "Qty",          w: "w-14" },
  { label: "Est. Total",   w: "w-28" },
  { label: "Lead Time",    w: "w-24" },
  { label: "Match Score",  w: "w-24" },
  { label: "Match Reason", w: "w-64" },
  { label: "Risk Notes",   w: "w-64" },
];

function TagCard({ tag, suppliers }: { tag: string; suppliers: QuoteRow[] }) {
  const top = suppliers[0];

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
      {/* Tag header */}
      <div className="flex items-center gap-3 px-4 py-3 bg-zinc-50 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
        <span className="font-mono text-sm font-bold text-zinc-800 dark:text-zinc-100">
          {tag}
        </span>
        <span className="text-xs text-zinc-400 dark:text-zinc-500">
          Recommended: {top.supplier}
        </span>
        <ScoreBadge score={top.match_score} />
      </div>

      {/* Supplier rows */}
      <div className="overflow-x-auto">
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
                    isTop ? "bg-emerald-50/40 dark:bg-emerald-900/10" : "hover:bg-zinc-50/50 dark:hover:bg-zinc-900/30"
                  }`}
                >
                  {/* Rank */}
                  <td className="w-12 px-3 py-2.5 whitespace-nowrap">
                    {isTop ? (
                      <span className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-700 dark:text-emerald-400">
                        #1
                        <span className="hidden sm:inline text-emerald-600 dark:text-emerald-500 font-normal">
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
                    <span className={`text-xs font-medium ${isTop ? "text-zinc-900 dark:text-zinc-100" : "text-zinc-700 dark:text-zinc-300"}`}>
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
                  <td className="w-64 px-3 py-2.5 text-xs text-zinc-500 dark:text-zinc-400">
                    {row.match_reason}
                  </td>

                  {/* Risk Notes */}
                  <td className="w-64 px-3 py-2.5 text-xs text-amber-700 dark:text-amber-400">
                    {row.risk_notes || "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function QuoteTable({ rows }: Props) {
  if (rows.length === 0)
    return (
      <p className="text-sm text-zinc-400 py-8 text-center">
        No recommendations available.
      </p>
    );

  const groups = groupByTag(rows);

  return (
    <div className="space-y-4">
      {Array.from(groups.entries()).map(([tag, suppliers]) => (
        <TagCard key={tag} tag={tag} suppliers={suppliers} />
      ))}
    </div>
  );
}
