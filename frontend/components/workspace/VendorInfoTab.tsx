"use client";

import { useState } from "react";
import type { RecommendationsResponse, QuoteRow } from "@/lib/types";

// ── Static supplier metadata mirrored from seed/suppliers.py ──────────────────

interface SupplierMeta {
  states: string[];
  openingTypes: string[];
  windowMaterials: string[];
  glassTypes: string[];
  reliabilityScore: number;
  notes: string;
  intro: string;
}

const SUPPLIER_META: Record<string, SupplierMeta> = {
  "Northline Glass Supply": {
    states: ["NY", "MI"],
    openingTypes: ["Casement", "Fixed", "Single-Hung"],
    windowMaterials: ["Aluminum", "Vinyl"],
    glassTypes: ["Clear", "Low-E"],
    reliabilityScore: 0.92,
    notes: "Strong regional presence in NY and MI. Specializes in aluminum casement windows.",
    intro: "A trusted regional supplier with deep coverage across New York and Michigan, Northline Glass Supply delivers reliable aluminum and vinyl window packages at consistent pricing. Their catalog covers casement, fixed, and single-hung configurations across a broad range of commercial project sizes.",
  },
  "BlueRidge Window Co.": {
    states: ["NY", "FL"],
    openingTypes: ["Fixed", "Awning", "Casement"],
    windowMaterials: ["Aluminum", "Fiberglass"],
    glassTypes: ["Clear", "Tinted"],
    reliabilityScore: 0.85,
    notes: "Lower-cost option. Longer lead time may create scheduling risk on tight projects.",
    intro: "BlueRidge Window Co. offers a cost-competitive window supply option for projects across New York and Florida, specializing in fixed, awning, and casement frames in aluminum and fiberglass. Their entry-point pricing makes them well-suited for budget-sensitive projects where lead time flexibility is available.",
  },
  "MetroFrame Systems": {
    states: ["MI", "NY"],
    openingTypes: ["Casement", "Double-Hung", "Single-Hung"],
    windowMaterials: ["Steel", "Aluminum"],
    glassTypes: ["Low-E", "Clear"],
    reliabilityScore: 0.95,
    notes: "Fastest lead time. Specializes in steel and aluminum commercial framing.",
    intro: "MetroFrame Systems is a high-performance commercial window supplier specializing in steel and aluminum framing with the fastest delivery times in the region. Their 95% reliability score and industry-leading lead times make them a top pick for schedule-critical builds across Michigan and New York.",
  },
  "ClearView Building Products": {
    states: ["FL", "MI"],
    openingTypes: ["Fixed", "Sliding", "Picture"],
    windowMaterials: ["Vinyl", "Fiberglass"],
    glassTypes: ["Clear", "Low-E"],
    reliabilityScore: 0.88,
    notes: "Best for large fixed and sliding windows. Competitive pricing on vinyl.",
    intro: "ClearView Building Products is the go-to supplier for large-format fixed and sliding windows, offering competitive vinyl and fiberglass options across Florida and Michigan. Their pricing is among the most competitive in the panel, making them strong candidates for value-driven specifications.",
  },
  "Sunbelt Architectural Windows": {
    states: ["FL"],
    openingTypes: ["Casement", "Fixed", "Awning", "Jalousie"],
    windowMaterials: ["Aluminum", "Wood"],
    glassTypes: ["Tinted", "Clear"],
    reliabilityScore: 0.82,
    notes: "Florida-only. Good for impact-rated and hurricane-zone requirements.",
    intro: "Sunbelt Architectural Windows is a Florida-exclusive supplier built for impact-rated and hurricane-zone window requirements. Specializing in aluminum and wood frames with tinted and clear glass, they serve clients who need coastal-grade building materials that meet strict regional compliance standards.",
  },
};

// ── Vendor aggregation ─────────────────────────────────────────────────────────

interface VendorSummary {
  name: string;
  avgMatchScore: number;
  minLeadTime: number;
  totalEstimated: number;
  bestUnitPrice: number;
  topMatchReason: string;
  topRiskNotes: string;
  meta: SupplierMeta | null;
}

function getTopVendors(quoteTable: QuoteRow[]): VendorSummary[] {
  const map = new Map<string, {
    scores: number[];
    leadTimes: number[];
    totals: number[];
    unitPrices: number[];
    reason: string;
    risk: string;
  }>();

  for (const row of quoteTable) {
    if (!map.has(row.supplier)) {
      map.set(row.supplier, {
        scores: [],
        leadTimes: [],
        totals: [],
        unitPrices: [],
        reason: row.match_reason ?? "",
        risk: row.risk_notes ?? "",
      });
    }
    const e = map.get(row.supplier)!;
    e.scores.push(row.match_score);
    e.leadTimes.push(row.lead_time_days);
    e.totals.push(row.estimated_total);
    e.unitPrices.push(row.unit_price);
  }

  const vendors: VendorSummary[] = [];
  for (const [name, d] of map) {
    const avg = d.scores.reduce((a, b) => a + b, 0) / d.scores.length;
    vendors.push({
      name,
      avgMatchScore: avg,
      minLeadTime: Math.min(...d.leadTimes),
      totalEstimated: d.totals.reduce((a, b) => a + b, 0),
      bestUnitPrice: Math.min(...d.unitPrices),
      topMatchReason: d.reason,
      topRiskNotes: d.risk,
      meta: SUPPLIER_META[name] ?? null,
    });
  }

  return vendors.sort((a, b) => b.avgMatchScore - a.avgMatchScore).slice(0, 3);
}

// ── Badge system ───────────────────────────────────────────────────────────────

type BadgeLabel = "Best Match" | "Fastest Lead Time" | "Cost Competitive" | "Regional Specialist";

const BADGE_CLS: Record<BadgeLabel, string> = {
  "Best Match":
    "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400",
  "Fastest Lead Time":
    "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
  "Cost Competitive":
    "bg-violet-100 text-violet-700 dark:bg-violet-900/30 dark:text-violet-400",
  "Regional Specialist":
    "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
};

function computeBadges(
  vendor: VendorSummary,
  all: VendorSummary[]
): { label: BadgeLabel; cls: string }[] {
  const result: { label: BadgeLabel; cls: string }[] = [];
  const maxScore = Math.max(...all.map((v) => v.avgMatchScore));
  const minLead = Math.min(...all.map((v) => v.minLeadTime));
  const minPrice = Math.min(...all.map((v) => v.bestUnitPrice));

  if (vendor.avgMatchScore >= maxScore - 0.001)
    result.push({ label: "Best Match", cls: BADGE_CLS["Best Match"] });
  if (vendor.minLeadTime <= minLead)
    result.push({ label: "Fastest Lead Time", cls: BADGE_CLS["Fastest Lead Time"] });
  if (vendor.bestUnitPrice <= minPrice + 0.01)
    result.push({ label: "Cost Competitive", cls: BADGE_CLS["Cost Competitive"] });
  if (vendor.meta && vendor.meta.states.length === 1)
    result.push({ label: "Regional Specialist", cls: BADGE_CLS["Regional Specialist"] });

  return result.slice(0, 2);
}

// ── Sub-components ─────────────────────────────────────────────────────────────

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-100 dark:border-zinc-800 px-3 py-2.5 text-center">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
        {label}
      </p>
      <p className="text-sm font-bold text-zinc-800 dark:text-zinc-200 mt-0.5">{value}</p>
    </div>
  );
}

function TagRow({ label, tags }: { label: string; tags: string[] }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500 w-16 shrink-0">
        {label}
      </span>
      <div className="flex flex-wrap gap-1">
        {tags.map((t) => (
          <span
            key={t}
            className="text-xs px-2 py-0.5 rounded-full bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400"
          >
            {t}
          </span>
        ))}
      </div>
    </div>
  );
}

function ImageCarousel({
  vendorIndex,
  vendorName,
}: {
  vendorIndex: number;
  vendorName: string;
}) {
  const [imgIdx, setImgIdx] = useState(0);
  const [failed, setFailed] = useState<Set<number>>(new Set());
  const total = 3;

  const prev = () => setImgIdx((i) => (i - 1 + total) % total);
  const next = () => setImgIdx((i) => (i + 1) % total);
  const path = `/vendor-demo/vendor-${vendorIndex}-${imgIdx + 1}.png`;

  return (
    <div className="relative rounded-xl overflow-hidden bg-zinc-100 dark:bg-zinc-800 aspect-[4/3] select-none">
      {!failed.has(imgIdx) ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={path}
          alt={`${vendorName} photo ${imgIdx + 1}`}
          className="w-full h-full object-cover"
          onError={() => setFailed((prev) => new Set([...prev, imgIdx]))}
        />
      ) : (
        <div className="w-full h-full flex flex-col items-center justify-center gap-1.5 text-zinc-300 dark:text-zinc-600">
          <span className="text-4xl font-bold">{vendorName[0]}</span>
          <span className="text-[11px]">No image</span>
        </div>
      )}

      {/* Prev / Next */}
      <button
        onClick={prev}
        aria-label="Previous image"
        className="absolute left-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-white/80 dark:bg-zinc-900/80 shadow flex items-center justify-center text-zinc-700 dark:text-zinc-300 hover:bg-white dark:hover:bg-zinc-800 transition-colors text-lg leading-none"
      >
        ‹
      </button>
      <button
        onClick={next}
        aria-label="Next image"
        className="absolute right-2 top-1/2 -translate-y-1/2 w-7 h-7 rounded-full bg-white/80 dark:bg-zinc-900/80 shadow flex items-center justify-center text-zinc-700 dark:text-zinc-300 hover:bg-white dark:hover:bg-zinc-800 transition-colors text-lg leading-none"
      >
        ›
      </button>

      {/* Dot indicators */}
      <div className="absolute bottom-2 left-1/2 -translate-x-1/2 flex gap-1.5">
        {Array.from({ length: total }).map((_, i) => (
          <button
            key={i}
            onClick={() => setImgIdx(i)}
            aria-label={`Image ${i + 1}`}
            className={`w-1.5 h-1.5 rounded-full transition-colors ${
              i === imgIdx ? "bg-white" : "bg-white/40"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

// ── Vendor card ────────────────────────────────────────────────────────────────

function VendorCard({
  vendor,
  vendorIndex,
  allVendors,
}: {
  vendor: VendorSummary;
  vendorIndex: number;
  allVendors: VendorSummary[];
}) {
  const badges = computeBadges(vendor, allVendors);
  const meta = vendor.meta;

  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 overflow-hidden shadow-sm">

      {/* ── Header ── */}
      <div className="px-6 py-5 flex items-start justify-between gap-4 border-b border-zinc-100 dark:border-zinc-800">
        <div className="space-y-1">
          <h3 className="text-base font-bold text-zinc-900 dark:text-zinc-100">
            {vendor.name}
          </h3>
          {meta && (
            <p className="text-xs text-zinc-500 dark:text-zinc-400">
              📍 {meta.states.join(" · ")}
            </p>
          )}
        </div>
        {badges.length > 0 && (
          <div className="flex flex-wrap gap-1.5 shrink-0 pt-0.5">
            {badges.map((b) => (
              <span
                key={b.label}
                className={`text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full ${b.cls}`}
              >
                {b.label}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* ── Vendor snapshot ── */}
      {meta?.intro && (
        <div className="px-6 py-4 border-b border-zinc-100 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-900/30">
          <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500 mb-1">
            Vendor Snapshot
          </p>
          <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
            {meta.intro}
          </p>
        </div>
      )}

      {/* ── Body ── */}
      <div className="px-6 py-5 grid grid-cols-1 md:grid-cols-5 gap-5">

        {/* Image carousel */}
        <div className="md:col-span-2">
          <ImageCarousel vendorIndex={vendorIndex} vendorName={vendor.name} />
        </div>

        {/* Fact panel */}
        <div className="md:col-span-3 space-y-4">
          {/* Metric boxes */}
          <div className="grid grid-cols-2 gap-2.5">
            <MetricBox label="Lead Time" value={`${vendor.minLeadTime} days`} />
            <MetricBox
              label="Match Score"
              value={`${Math.round(vendor.avgMatchScore * 100)}%`}
            />
            {meta && (
              <MetricBox
                label="Reliability"
                value={`${Math.round(meta.reliabilityScore * 100)}%`}
              />
            )}
            <MetricBox
              label="From"
              value={`$${vendor.bestUnitPrice.toFixed(0)} / unit`}
            />
          </div>

          {/* Material / glass / opening tags */}
          {meta && (
            <div className="space-y-2 pt-1">
              <TagRow label="Materials" tags={meta.windowMaterials} />
              <TagRow label="Glass" tags={meta.glassTypes} />
              <TagRow label="Openings" tags={meta.openingTypes} />
            </div>
          )}
        </div>
      </div>

      {/* ── Why recommended ── */}
      {(vendor.topMatchReason || meta?.notes) && (
        <div className="px-6 pb-5">
          <div className="rounded-lg bg-zinc-50 dark:bg-zinc-900/60 border border-zinc-100 dark:border-zinc-800 px-4 py-3 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-zinc-400 dark:text-zinc-500">
              Why recommended
            </p>
            <p className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
              {vendor.topMatchReason || meta?.notes}
            </p>
            {vendor.topRiskNotes && (
              <p className="text-xs text-amber-600 dark:text-amber-400">
                ⚠ {vendor.topRiskNotes}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Empty state ────────────────────────────────────────────────────────────────

function EmptyState({ onSwitchToQuote }: { onSwitchToQuote: () => void }) {
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-10 text-center space-y-4">
      <div className="w-12 h-12 rounded-full bg-zinc-100 dark:bg-zinc-800 flex items-center justify-center mx-auto">
        <svg
          className="w-6 h-6 text-zinc-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4"
          />
        </svg>
      </div>
      <div className="space-y-1">
        <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
          No vendor profiles yet
        </p>
        <p className="text-sm text-zinc-400 dark:text-zinc-500">
          Generate a quote first to view recommended vendor profiles.
        </p>
      </div>
      <button
        onClick={onSwitchToQuote}
        className="px-5 py-2 rounded-lg bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 text-sm font-medium hover:bg-zinc-700 dark:hover:bg-zinc-300 transition-colors"
      >
        Generate Quote
      </button>
    </div>
  );
}

// ── Main export ────────────────────────────────────────────────────────────────

export function VendorInfoTab({
  recommendations,
  onSwitchToQuote,
}: {
  recommendations: RecommendationsResponse | null;
  onSwitchToQuote: () => void;
}) {
  if (!recommendations || recommendations.quote_table.length === 0) {
    return <EmptyState onSwitchToQuote={onSwitchToQuote} />;
  }

  const vendors = getTopVendors(recommendations.quote_table);

  return (
    <div className="space-y-6">
      {/* Section header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">
            Recommended Vendors
          </h2>
          <p className="text-xs text-zinc-500 dark:text-zinc-400 mt-0.5">
            Top {vendors.length} suppliers matched to your project window schedule.
          </p>
        </div>
        <span className="text-[10px] font-semibold uppercase tracking-wide px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400">
          {vendors.length} Vendors
        </span>
      </div>

      {/* Vendor cards */}
      {vendors.map((vendor, i) => (
        <VendorCard
          key={vendor.name}
          vendor={vendor}
          vendorIndex={i + 1}
          allVendors={vendors}
        />
      ))}
    </div>
  );
}
