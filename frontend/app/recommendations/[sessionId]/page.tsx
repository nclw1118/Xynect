"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { RecommendationsResponse } from "@/lib/types";
import { QuoteTable } from "@/components/QuoteTable";
import { RecommendationSummary } from "@/components/RecommendationSummary";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function RecommendationsPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    apiFetch<RecommendationsResponse>(`/api/sessions/${sessionId}/recommendations`)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load."));
  }, [sessionId]);

  if (error)
    return (
      <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950 px-6">
        <div className="text-center space-y-3">
          <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
          <a href="/upload" className="text-sm underline text-zinc-500">← Start over</a>
        </div>
      </main>
    );

  if (!data)
    return (
      <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950">
        <p className="text-zinc-400 text-sm">Loading recommendations…</p>
      </main>
    );

  return (
    <main className="min-h-screen bg-white dark:bg-zinc-950 px-4 py-10">
      <div className="max-w-6xl mx-auto space-y-8">

        {/* Header */}
        <div className="flex items-start justify-between flex-wrap gap-4">
          <div>
            <p className="text-xs font-mono tracking-widest text-zinc-400 uppercase mb-1">
              Recommendations
            </p>
            <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
              Supplier &amp; Pricing Recommendations
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
              {data.quote_table.length} quote{data.quote_table.length !== 1 ? "s" : ""} across{" "}
              {new Set(data.quote_table.map((r) => r.tag)).size} window{" "}
              {new Set(data.quote_table.map((r) => r.tag)).size !== 1 ? "tags" : "tag"}
            </p>
          </div>
          <Link
            href="/upload"
            className={cn(buttonVariants({ variant: "outline" }), "text-sm")}
          >
            Start New Upload
          </Link>
        </div>

        {/* Quote table */}
        <section className="space-y-2">
          <h2 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
            Quote Table
          </h2>
          <QuoteTable rows={data.quote_table} />
        </section>

        {/* Natural-language summary */}
        <RecommendationSummary summary={data.natural_language_summary} />

      </div>
    </main>
  );
}
