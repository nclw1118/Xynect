export const metadata = {
  title: "Processing — Xynect",
};

export default async function ProcessingPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-white dark:bg-zinc-950 px-6">
      <div className="text-center space-y-4 max-w-sm">
        <p className="text-xs font-mono tracking-widest text-zinc-400 uppercase">
          Processing
        </p>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Analyzing your file…
        </h1>
        <p className="text-sm text-zinc-500 dark:text-zinc-400">
          Extraction progress will appear here in the next phase.
        </p>
        <p className="text-xs font-mono text-zinc-300 dark:text-zinc-700 break-all">
          {sessionId}
        </p>
      </div>
    </main>
  );
}
