"use client";

import type { WindowItem } from "@/lib/types";

interface Props {
  items: WindowItem[];
  onChange: (updated: WindowItem[]) => void;
}

// ── Dimension helpers ──────────────────────────────────────────────────────────

/** Parse any dimension string to a number in inches, return null if unparseable. */
function toInches(s: string | null | undefined): number | null {
  if (!s) return null;
  const v = s.trim().toLowerCase();
  // feet-inches compound: 3'-6", 3'6"
  const compound = v.match(/^([\d.]+)\s*'\s*-?\s*([\d.]+)/);
  if (compound) return parseFloat(compound[1]) * 12 + parseFloat(compound[2]);
  // feet: 3 ft, 3.5 ft, 3'
  const ft = v.match(/^([\d.]+)\s*(?:ft|feet|')\b/);
  if (ft) return parseFloat(ft[1]) * 12;
  // inches or bare number
  const num = v.match(/^([\d.]+)/);
  if (num) return parseFloat(num[1]);
  return null;
}

/** Extract the numeric portion of a dimension for display (in the "in" input). */
function displayInches(s: string | null | undefined): string {
  const inches = toInches(s);
  if (inches === null) return "";
  // Round to 4 sig figs to avoid floating-point noise (e.g. 12.000000000000002)
  const rounded = parseFloat(inches.toFixed(4));
  return String(rounded);
}

/** Extract the numeric portion for unitless numeric fields (u_value, shgc, vt, quantity). */
function displayNumeric(s: string | null | undefined): string {
  if (!s) return "";
  const m = s.trim().match(/^([\d.]+)/);
  return m ? m[1] : "";
}

/** Auto-calculate area in sf from two dimension strings. */
function calcAreaSf(w: string | null | undefined, h: string | null | undefined): string | null {
  const wIn = toInches(w);
  const hIn = toInches(h);
  if (wIn === null || hIn === null) return null;
  const sf = (wIn / 12) * (hIn / 12);
  const rounded = parseFloat(sf.toFixed(4));
  return rounded === Math.floor(rounded) ? `${Math.floor(rounded)} sf` : `${rounded.toFixed(2)} sf`;
}

// ── Column definitions ─────────────────────────────────────────────────────────

type ColDef = {
  key: keyof WindowItem;
  label: string;
  width: string;
  type: "text" | "inches" | "area" | "integer" | "numeric" | "readonly";
};

const COLS: ColDef[] = [
  { key: "tag",          label: "Tag",          width: "w-20",  type: "text"     },
  { key: "material_type",label: "Type",         width: "w-20",  type: "readonly" },
  { key: "width",        label: "Width",        width: "w-28",  type: "inches"   },
  { key: "height",       label: "Height",       width: "w-28",  type: "inches"   },
  { key: "area",         label: "Area",         width: "w-24",  type: "area"     },
  { key: "quantity",     label: "Qty",          width: "w-20",  type: "integer"  },
  { key: "opening_type", label: "Opening Type", width: "w-32",  type: "text"     },
  { key: "material",     label: "Material",     width: "w-28",  type: "text"     },
  { key: "u_value",      label: "U-Value",      width: "w-22",  type: "numeric"  },
  { key: "shgc",         label: "SHGC",         width: "w-20",  type: "numeric"  },
  { key: "vt",           label: "VT",           width: "w-20",  type: "numeric"  },
  { key: "glass_type",   label: "Glass Type",   width: "w-28",  type: "text"     },
  { key: "confidence",   label: "Conf",         width: "w-16",  type: "readonly" },
  { key: "notes",        label: "Notes",        width: "w-48",  type: "text"     },
];

// ── Cell components ────────────────────────────────────────────────────────────

const BASE_INPUT =
  "rounded px-2 py-1 text-xs outline-none transition-colors focus:ring-1 focus:ring-zinc-400 dark:focus:ring-zinc-500";
const FILLED = "bg-transparent border border-transparent hover:border-zinc-200 dark:hover:border-zinc-700 text-zinc-900 dark:text-zinc-100";
const EMPTY = "bg-amber-50 border border-amber-200 placeholder:text-amber-400 dark:bg-amber-900/20 dark:border-amber-700 dark:placeholder:text-amber-600 text-zinc-400";

function Cell({
  col,
  item,
  onCellChange,
}: {
  col: ColDef;
  item: WindowItem;
  onCellChange: (key: keyof WindowItem, rawVal: string) => void;
}) {
  // ── Read-only ──
  if (col.type === "readonly") {
    if (col.key === "confidence") {
      const raw = item.confidence;
      const display = raw != null ? `${Math.round(Number(raw) * 100)}%` : "—";
      return (
        <td className={`${col.width} px-2 py-1.5 text-xs text-zinc-400 dark:text-zinc-500 text-center whitespace-nowrap`}>
          {display}
        </td>
      );
    }
    return (
      <td className={`${col.width} px-2 py-1.5 text-xs text-zinc-500 dark:text-zinc-400 whitespace-nowrap`}>
        {String(item[col.key] ?? "")}
      </td>
    );
  }

  // ── Width / Height — numeric input + "in" unit ──
  if (col.type === "inches") {
    const display = displayInches(item[col.key] as string | null);
    const empty = !display;
    return (
      <td className={`${col.width} px-1 py-1`}>
        <div className="flex items-center gap-1">
          <input
            type="number"
            min="0"
            step="0.01"
            value={display}
            onChange={(e) => onCellChange(col.key, e.target.value)}
            placeholder="—"
            className={`w-16 ${BASE_INPUT} ${empty ? EMPTY : FILLED} [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none`}
          />
          <span className={`text-xs shrink-0 ${empty ? "text-amber-400 dark:text-amber-600" : "text-zinc-400 dark:text-zinc-500"}`}>
            in
          </span>
        </div>
      </td>
    );
  }

  // ── Area — computed read-only display ──
  if (col.type === "area") {
    const computed = calcAreaSf(item.width, item.height);
    const display = computed ?? displayNumeric(item.area);
    const empty = !display;
    return (
      <td className={`${col.width} px-2 py-1.5 whitespace-nowrap`}>
        <div className="flex items-center gap-1">
          <span className={`text-xs ${empty ? "text-zinc-300 dark:text-zinc-600" : "text-zinc-600 dark:text-zinc-300"}`}>
            {display ? display.replace(" sf", "") : "—"}
          </span>
          <span className={`text-xs shrink-0 ${empty ? "text-zinc-300 dark:text-zinc-600" : "text-zinc-400 dark:text-zinc-500"}`}>
            {display ? "sf" : ""}
          </span>
        </div>
      </td>
    );
  }

  // ── Quantity — integer input ──
  if (col.type === "integer") {
    const display = displayNumeric(item[col.key] as string | null);
    const empty = !display;
    return (
      <td className={`${col.width} px-1 py-1`}>
        <input
          type="number"
          min="0"
          step="1"
          value={display}
          onChange={(e) => onCellChange(col.key, e.target.value)}
          placeholder="—"
          className={`w-full ${BASE_INPUT} ${empty ? EMPTY : FILLED} [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none`}
        />
      </td>
    );
  }

  // ── U-Value / SHGC / VT — numeric input (no unit label) ──
  if (col.type === "numeric") {
    const display = displayNumeric(item[col.key] as string | null);
    const empty = !display;
    return (
      <td className={`${col.width} px-1 py-1`}>
        <input
          type="number"
          min="0"
          max="9.99"
          step="0.01"
          value={display}
          onChange={(e) => onCellChange(col.key, e.target.value)}
          placeholder="—"
          className={`w-full ${BASE_INPUT} ${empty ? EMPTY : FILLED} [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none`}
        />
      </td>
    );
  }

  // ── Generic text input ──
  const raw = item[col.key];
  const value = raw !== null && raw !== undefined ? String(raw) : "";
  const empty = !value;
  return (
    <td className={`${col.width} px-1 py-1`}>
      <input
        type="text"
        value={value}
        onChange={(e) => onCellChange(col.key, e.target.value)}
        placeholder="Missing — optional"
        className={`w-full ${BASE_INPUT} ${empty ? EMPTY : FILLED}`}
      />
    </td>
  );
}

// ── Table ──────────────────────────────────────────────────────────────────────

export function EditableWindowTable({ items, onChange }: Props) {
  const handleChange = (rowIdx: number, key: keyof WindowItem, rawVal: string) => {
    const item = items[rowIdx];
    const updates: Partial<WindowItem> = {};

    if (key === "width" || key === "height") {
      // Store as "N in" so backend helpers (parse_dimension_to_feet, _to_inches) resolve correctly
      updates[key] = rawVal ? `${rawVal} in` : null;
      const newWidth  = key === "width"  ? updates[key] : item.width;
      const newHeight = key === "height" ? updates[key] : item.height;
      updates.area = calcAreaSf(newWidth, newHeight) ?? item.area ?? null;
    } else if (key === "quantity") {
      if (!rawVal) {
        updates.quantity = null;
      } else {
        const intVal = parseInt(rawVal, 10);
        updates.quantity = isNaN(intVal) ? null : String(intVal);
      }
    } else if (key === "u_value" || key === "shgc" || key === "vt") {
      updates[key] = rawVal || null;
    } else {
      (updates as Record<string, string | null>)[key as string] = rawVal || null;
    }

    const next = items.map((it, i) =>
      i === rowIdx ? { ...it, ...updates } : it
    );
    onChange(next);
  };

  if (items.length === 0)
    return (
      <p className="text-sm text-zinc-400 text-center py-8">
        No window items extracted. Click "+ Add Window" to add one manually.
      </p>
    );

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="bg-zinc-50 dark:bg-zinc-900 border-b border-zinc-200 dark:border-zinc-800">
              {COLS.map((col) => (
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
                {COLS.map((col) => (
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
