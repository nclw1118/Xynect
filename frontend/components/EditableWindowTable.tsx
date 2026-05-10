"use client";

import type { WindowItem } from "@/lib/types";

interface Props {
  items: WindowItem[];
  onChange: (updated: WindowItem[]) => void;
}

const EDITABLE_COLS: { key: keyof WindowItem; label: string; width: string }[] = [
  { key: "tag",          label: "Tag",          width: "w-20" },
  { key: "material_type",label: "Material Type", width: "w-28" },
  { key: "width",        label: "Width",         width: "w-24" },
  { key: "height",       label: "Height",        width: "w-24" },
  { key: "area",         label: "Area",          width: "w-24" },
  { key: "quantity",     label: "Quantity",      width: "w-20" },
  { key: "opening_type", label: "Opening Type",  width: "w-32" },
  { key: "material",     label: "Material",      width: "w-28" },
  { key: "u_value",      label: "U-Value",       width: "w-20" },
  { key: "shgc",         label: "SHGC",          width: "w-20" },
  { key: "vt",           label: "VT",            width: "w-20" },
  { key: "glass_type",   label: "Glass Type",    width: "w-28" },
  { key: "confidence",   label: "Confidence",    width: "w-24" },
  { key: "notes",        label: "Notes",         width: "w-48" },
];

const READ_ONLY = new Set<keyof WindowItem>(["confidence", "material_type"]);

function Cell({
  col,
  item,
  onCellChange,
}: {
  col: (typeof EDITABLE_COLS)[number];
  item: WindowItem;
  onCellChange: (key: keyof WindowItem, val: string) => void;
}) {
  const raw = item[col.key];
  const value = raw !== null && raw !== undefined ? String(raw) : "";

  if (col.key === "confidence") {
    return (
      <td className={`${col.width} px-2 py-1.5 text-xs text-zinc-400 text-center whitespace-nowrap`}>
        {value ? `${Math.round(Number(value) * 100)}%` : "—"}
      </td>
    );
  }

  if (READ_ONLY.has(col.key)) {
    return (
      <td className={`${col.width} px-2 py-1.5 text-xs text-zinc-500 whitespace-nowrap`}>
        {value}
      </td>
    );
  }

  const empty = !value;
  return (
    <td className={`${col.width} px-1 py-1`}>
      <input
        type="text"
        value={value}
        onChange={(e) => onCellChange(col.key, e.target.value)}
        placeholder="Missing — optional"
        className={`w-full rounded px-2 py-1 text-xs outline-none transition-colors
          focus:ring-1 focus:ring-zinc-400 dark:focus:ring-zinc-500
          ${
            empty
              ? "bg-amber-50 border border-amber-200 placeholder:text-amber-400 dark:bg-amber-900/20 dark:border-amber-700 dark:placeholder:text-amber-600 text-zinc-400"
              : "bg-transparent border border-transparent hover:border-zinc-200 dark:hover:border-zinc-700 text-zinc-900 dark:text-zinc-100"
          }`}
      />
    </td>
  );
}

export function EditableWindowTable({ items, onChange }: Props) {
  const handleChange = (rowIdx: number, key: keyof WindowItem, val: string) => {
    const next = items.map((item, i) =>
      i === rowIdx ? { ...item, [key]: val || null } : item
    );
    onChange(next);
  };

  if (items.length === 0)
    return (
      <p className="text-sm text-zinc-400 text-center py-8">
        No window items were extracted.
      </p>
    );

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-zinc-50 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
              {EDITABLE_COLS.map((col) => (
                <th
                  key={col.key}
                  className={`${col.width} px-2 py-2 text-left text-xs font-semibold text-zinc-500 dark:text-zinc-400 whitespace-nowrap`}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item, rowIdx) => (
              <tr
                key={item.id}
                className="border-b border-zinc-100 dark:border-zinc-800 last:border-0 hover:bg-zinc-50/50 dark:hover:bg-zinc-900/30"
              >
                {EDITABLE_COLS.map((col) => (
                  <Cell
                    key={col.key}
                    col={col}
                    item={item}
                    onCellChange={(k, v) => handleChange(rowIdx, k, v)}
                  />
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
