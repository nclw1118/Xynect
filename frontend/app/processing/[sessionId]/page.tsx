import { AgentProgress } from "@/components/AgentProgress";

export const metadata = { title: "Processing — Xynect" };

export default async function ProcessingPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;
  return (
    <main className="flex min-h-screen items-center justify-center bg-white dark:bg-zinc-950 px-6">
      <AgentProgress sessionId={sessionId} />
    </main>
  );
}
