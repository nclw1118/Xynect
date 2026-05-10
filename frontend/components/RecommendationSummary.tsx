interface Props {
  summary: string;
}

export function RecommendationSummary({ summary }: Props) {
  const paragraphs = summary.split("\n\n").filter(Boolean);
  return (
    <div className="rounded-xl border border-zinc-200 dark:border-zinc-800 p-5 space-y-3 bg-zinc-50 dark:bg-zinc-900/40">
      <h3 className="text-sm font-semibold text-zinc-700 dark:text-zinc-300">
        Recommendation Summary
      </h3>
      <div className="space-y-3">
        {paragraphs.map((p, i) => (
          <p key={i} className="text-sm text-zinc-600 dark:text-zinc-400 leading-relaxed">
            {p}
          </p>
        ))}
      </div>
    </div>
  );
}
