"use client";

import { useEffect, useRef, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ProgressResponse } from "@/lib/types";
import AgentPanel from "./AgentPanel";
import WorkspaceTabs from "./WorkspaceTabs";

const TERMINAL = new Set([
  "review_ready",
  "confirmed",
  "recommendation_ready",
  "error",
]);

export default function WorkspaceShell({ sessionId }: { sessionId: string }) {
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [isPolling, setIsPolling] = useState(true);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await apiFetch<ProgressResponse>(
          `/api/sessions/${sessionId}/progress`
        );
        setProgress(data);
        if (TERMINAL.has(data.status)) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setIsPolling(false);
        }
      } catch {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setIsPolling(false);
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 800);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [sessionId]);

  const extractionReady =
    progress !== null &&
    progress.status !== "processing" &&
    progress.status !== "error";

  return (
    <div className="flex h-screen overflow-hidden bg-white dark:bg-zinc-950">
      <AgentPanel progress={progress} isPolling={isPolling} />
      <div className="flex-1 min-w-0 overflow-hidden flex flex-col">
        <WorkspaceTabs sessionId={sessionId} extractionReady={extractionReady} />
      </div>
    </div>
  );
}
