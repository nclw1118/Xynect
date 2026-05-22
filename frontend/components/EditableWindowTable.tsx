"use client";

import { useState } from "react";
import type { WindowItem } from "@/lib/types";
import { parseDimParts, buildArchValue, calcAreaSf } from "@/lib/unit-utils";

interface Props {
  items: WindowItem[];
  onChange: (updated: WindowItem[]) => void;
}

/** Extract the numeric portion for unitless numeric fields (u_value, shgc, vt, quantity). */
function displayNumeric(s: string | null | undefined): string {
  if (!s) return "";
  const m = s.trim().match(/^([\d.]+)/);
  return m ? m[1] : "";
}

// ── Column definitions ─────────────────────────────────────────────────────────

type ColDef = {
  key: keyof WindowItem;
  label: string;
  width: string;
  type: "text" | "ft-inches" | "area" | "integer" | "numeric" | "readonly";
};

const COLS: ColDef[] = [
  { key: "tag",          label: "Tag",          width: "w-20",  type: "text"      },
  { key: "material_type",label: "Type",         width: "w-20",  type: "readonly"  },
  { key: "width",        label: "Width",        width: "w-28",  type: "ft-inches" },
  { key: "height",       label: "Height",       width: "w-28",  type: "ft-inches" },
  { key: "area",         label: "Area",         width: "w-24",  type: "area"      },
  { key: "quantity",     label: "Qty",          width: "w-20",  type: "integer"   },
  { key: "opening_type", label: "Opening Type", width: "w-32",  type: "text"      },
  { key: "material",     label: "Material",     width: "w-28",  type: "text"      },
  { key: "u_value",      label: "U-Value",      width: "w-22",  type: "numeric"   },
  { key: "shgc",         label: "SHGC",         width: "w-20",  type: "numeric"   },
  { key: "vt",           label: "VT",           width: "w-20",  type: "numeric"   },
  { key: "glass_type",   label: "Glass Type",   width: "w-28",  type: "text"      },
  { key: "confidence",   label: "Conf",         width: "w-16",  type: "readonly"  },
  { key: "notes",        label: "Notes",        width: "w-48",  type: "text"      },
];

// ── Shared input styles ────────────────────────────────────────────────────────

const BASE_INPUT =
  "rounded px-2 py-1 text-xs outline-none transition-colors focus:ring-1 focus:ring-zinc-400 dark:focus:ring-zinc-500";
const FILLED = "bg-transparent border border-transparent hover:border-zinc-200 dark:hover:border-zinc-700 text-zinc-900 dark:text-zinc-100";
const EMPTY  = "bg-amber-50 border border-amber-200 placeholder:text-amber-400 dark:bg-amber-900/20 dark:border-amber-700 dark:placeholder:text-amber-600 text-zinc-400";
const SPIN   = "[appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none";

// ── Feet + inches cell ─────────────────────────────────────────────────────────

function FtInCell({
  colKey,
  colWidth,
  stored,
  onCellChange,
}: {
  colKey: "width" | "height";
  colWidth: string;
  stored: string | null;
  onCellChange: (key: "width" | "height", rawVal: string) => void;
}) {
  const parts = parseDimParts(stored);
  const [ftStr, setFtStr] = useState(parts !== null ? String(parts.ft) : "");
  const [inStr, setInStr] = useState(parts !== null ? String(parts.inches) : "");
  const empty = ftStr === "" && inStr === "";

  const commit = (ft: string, inches: string) => {
    onCellChange(colKey, buildArchValue(ft, inches) ?? "");
  };

  const unitCls = `text-xs leading-none shrink-0 pr-1 ${empty ? "text-amber-400 dark:text-amber-600" : "text-zinc-400 dark:text-zinc-500"}`;

  return (
    <td className={`${colWidth} px-1 py-1`}>
      <div className="flex items-center">
        <input
          type="number"
          min="0"
          step="1"
          value={ftStr}
          onChange={(e) => {
            setFtStr(e.target.value);
            commit(e.target.value, inStr);
          }}
          placeholder="—"
          className={`w-9 ${BASE_INPUT} ${empty ? EMPTY : FILLED} ${SPIN}`}
        />
        <span className={unitCls}>′</span>
        <input
          type="number"
          min="0"
          max="11.99"
          step="0.01"
          value={inStr}
          onChange={(e) => {
            setInStr(e.target.value);
            commit(ftStr, e.target.value);
          }}
          placeholder="—"
          className={`w-9 ${BASE_INPUT} ${empty ? EMPTY : FILLED} ${SPIN}`}
        />
        <span className={unitCls}>″</span>
      </div>
    </td>
  );
}

// ── Generic cell ───────────────────────────────────────────────────────────────

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

  // ── Width / Height — ft + inches inputs ──
  if (col.type === "ft-inches") {
    return (
      <FtInCell
        colKey={col.key as "width" | "height"}
        colWidth={col.width}
        stored={item[col.key] as string | null}
        onCellChange={onCellChange as (key: "width" | "height", rawVal: string) => void}
      />
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
          className={`w-full ${BASE_INPUT} ${empty ? EMPTY : FILLED} ${SPIN}`}
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
          className={`w-full ${BASE_INPUT} ${empty ? EMPTY : FILLED} ${SPIN}`}
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
      // rawVal is already architectural notation like "3'-6"" or ""
      updates[key] = rawVal || null;
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
        No window items extracted. Click &ldquo;+ Add Window&rdquo; to add one manually.
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
