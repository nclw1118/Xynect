"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import type { DoorItem } from "@/lib/types";
import { parseDimParts, buildArchValue, calcAreaSf } from "@/lib/unit-utils";

interface Props {
  items: DoorItem[];
  onChange: (updated: DoorItem[]) => void;
}

/** Extract the numeric portion for unitless numeric fields (quantity). */
function displayNumeric(s: string | null | undefined): string {
  if (!s) return "";
  const m = s.trim().match(/^([\d.]+)/);
  return m ? m[1] : "";
}

// ── Column definitions ─────────────────────────────────────────────────────────

type ColDef = {
  key: keyof DoorItem;
  label: string;
  width: string;
  type: "text" | "ft-inches" | "area" | "integer" | "readonly" | "notes";
};

const COLS: ColDef[] = [
  { key: "tag",          label: "Tag",          width: "w-20",  type: "text"      },
  { key: "opening_type", label: "Type",         width: "w-32",  type: "text"      },
  { key: "quantity",     label: "Qty",          width: "w-20",  type: "integer"   },
  { key: "width",        label: "Width",        width: "w-28",  type: "ft-inches" },
  { key: "height",       label: "Height",       width: "w-28",  type: "ft-inches" },
  { key: "area",         label: "Area",         width: "w-24",  type: "area"      },
  { key: "material",     label: "Material",     width: "w-28",  type: "text"      },
  { key: "fire_rating",  label: "Fire Rating",  width: "w-24",  type: "text"      },
  { key: "self_closing", label: "Self Closing", width: "w-24",  type: "text"      },
  { key: "glass_type",   label: "Glass Type",   width: "w-28",  type: "text"      },
  { key: "confidence",   label: "Conf",         width: "w-16",  type: "readonly"  },
  { key: "notes",        label: "Notes",        width: "w-48",  type: "notes"     },
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

// ── Notes cell — editable input + hover tooltip ────────────────────────────────

interface TooltipPos { x: number; y: number; }

function NotesCell({
  colKey,
  colWidth,
  value,
  onCellChange,
}: {
  colKey: keyof DoorItem;
  colWidth: string;
  value: string;
  onCellChange: (key: keyof DoorItem, rawVal: string) => void;
}) {
  const [pos, setPos] = useState<TooltipPos | null>(null);
  const [isFocused, setIsFocused] = useState(false);
  const empty = !value;
  const showTooltip = pos !== null && !isFocused && !empty;

  return (
    <td className={`${colWidth} px-1 py-1`}>
      <div
        onMouseEnter={(e) => {
          if (empty) return;
          const r = e.currentTarget.getBoundingClientRect();
          setPos({ x: r.left, y: r.top });
        }}
        onMouseLeave={() => setPos(null)}
        className="relative"
      >
        <input
          type="text"
          value={value}
          onChange={(e) => onCellChange(colKey, e.target.value)}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          placeholder="Missing — optional"
          className={`w-full ${BASE_INPUT} ${empty ? EMPTY : FILLED} text-ellipsis`}
        />
      </div>

      {showTooltip && createPortal(
        <div
          style={{
            position: "fixed",
            left: Math.min(pos!.x, typeof window !== "undefined" ? window.innerWidth - 308 : pos!.x),
            top: pos!.y - 10,
            transform: "translateY(-100%)",
            zIndex: 9999,
          }}
          className="w-72 bg-zinc-900 dark:bg-zinc-50 text-zinc-100 dark:text-zinc-900 text-xs leading-relaxed rounded-xl px-3 py-2.5 shadow-2xl pointer-events-none whitespace-pre-wrap break-words"
        >
          {value}
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
  item: DoorItem;
  onCellChange: (key: keyof DoorItem, rawVal: string) => void;
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

  // ── Notes — editable + hover tooltip ──
  if (col.type === "notes") {
    const raw = item[col.key];
    const value = raw !== null && raw !== undefined ? String(raw) : "";
    return (
      <NotesCell
        colKey={col.key}
        colWidth={col.width}
        value={value}
        onCellChange={onCellChange}
      />
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

export function EditableDoorTable({ items, onChange }: Props) {
  const handleChange = (rowIdx: number, key: keyof DoorItem, rawVal: string) => {
    const item = items[rowIdx];
    const updates: Partial<DoorItem> = {};

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
        No door items extracted. Click &ldquo;+ Add Door&rdquo; to add one manually.
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
