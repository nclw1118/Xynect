"use client";

import type { ProjectInfo } from "@/lib/types";

const SUPPORTED_STATES = ["MI", "NY", "FL"];

interface Props {
  info: ProjectInfo | null;
  onChange: (updated: Partial<ProjectInfo>) => void;
}

function Field({
  label,
  value,
  onChange,
  readOnly,
}: {
  label: string;
  value: string | null;
  onChange?: (v: string) => void;
  readOnly?: boolean;
}) {
  const empty = !value;
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
        {label}
      </label>
      {readOnly ? (
        <p className="text-sm text-zinc-700 dark:text-zinc-300">
          {value || <span className="text-zinc-400 italic">—</span>}
        </p>
      ) : (
        <input
          type="text"
          value={value ?? ""}
          onChange={(e) => onChange?.(e.target.value)}
          placeholder="Missing — optional"
          className={`rounded-md border px-3 py-1.5 text-sm outline-none transition-colors
            focus:ring-2 focus:ring-zinc-300 dark:focus:ring-zinc-600
            ${
              empty
                ? "border-amber-300 bg-amber-50 placeholder:text-amber-400 dark:border-amber-700 dark:bg-amber-900/20 dark:placeholder:text-amber-600"
                : "border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100"
            }`}
        />
      )}
    </div>
  );
}

export function ProjectInfoForm({ info, onChange }: Props) {
  const emit = (key: keyof ProjectInfo) => (val: string) =>
    onChange({ [key]: val || null });

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-5 space-y-4">
      <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        Project Information
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <Field label="Project Name" value={info?.project_name ?? null} onChange={emit("project_name")} />
        <Field label="Site Address" value={info?.site_address ?? null} onChange={emit("site_address")} />
        <Field label="City" value={info?.city ?? null} onChange={emit("city")} />

        {/* State — select */}
        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-zinc-500 dark:text-zinc-400 uppercase tracking-wide">
            State
          </label>
          <select
            value={info?.state ?? ""}
            onChange={(e) => onChange({ state: e.target.value || null })}
            className={`rounded-md border px-3 py-1.5 text-sm outline-none transition-colors
              focus:ring-2 focus:ring-zinc-300 dark:focus:ring-zinc-600
              ${
                !info?.state
                  ? "border-amber-300 bg-amber-50 text-amber-500 dark:border-amber-700 dark:bg-amber-900/20"
                  : "border-zinc-200 bg-white dark:border-zinc-700 dark:bg-zinc-900 text-zinc-900 dark:text-zinc-100"
              }`}
          >
            <option value="">Missing — optional</option>
            {SUPPORTED_STATES.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </div>

        <Field label="Zip Code" value={info?.zip_code ?? null} onChange={emit("zip_code")} />
        <Field label="Detected File Type" value={info?.detected_file_type ?? null} readOnly />
      </div>
    </div>
  );
}
