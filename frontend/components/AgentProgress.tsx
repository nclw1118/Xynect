"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import type { ProgressResponse, ProgressStep } from "@/lib/types";

function StepIcon({ status }: { status: ProgressStep["status"] }) {
  if (status === "completed")
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 text-white text-xs">
        ✓
      </span>
    );
  if (status === "active")
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-zinc-400 border-t-zinc-800 dark:border-zinc-600 dark:border-t-zinc-100 animate-spin" />
    );
  if (status === "error")
    return (
      <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-white text-xs">
        ✕
      </span>
    );
  return (
    <span className="flex h-5 w-5 items-center justify-center rounded-full border-2 border-zinc-200 dark:border-zinc-700" />
  );
}

export function AgentProgress({ sessionId }: { sessionId: string }) {
  const router = useRouter();
  const [progress, setProgress] = useState<ProgressResponse | null>(null);
  const [fatalError, setFatalError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const data = await apiFetch<ProgressResponse>(
          `/api/sessions/${sessionId}/progress`
        );
        setProgress(data);

        if (data.status === "review_ready") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          router.push(`/workspace/${sessionId}`);
        } else if (data.status === "error") {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setFatalError("Extraction failed. Please go back and try a different file.");
        }
      } catch (err) {
        setFatalError(err instanceof Error ? err.message : "Failed to reach the server.");
        if (intervalRef.current) clearInterval(intervalRef.current);
      }
    };

    poll();
    intervalRef.current = setInterval(poll, 800);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [sessionId, router]);

  if (fatalError)
    return (
      <div className="text-center space-y-4">
        <p className="text-red-600 dark:text-red-400 text-sm">{fatalError}</p>
        <a
          href="/upload"
          className="text-sm underline text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
        >
          ← Back to upload
        </a>
      </div>
    );

  return (
    <div className="w-full max-w-sm space-y-6">
      <div className="text-center space-y-2">
        <p className="text-xs font-mono tracking-widest text-zinc-400 uppercase">
          Processing
        </p>
        <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
          Analyzing your file…
        </h1>
        {progress?.current_step && (
          <p className="text-sm text-zinc-500 dark:text-zinc-400">
            {progress.current_step}
          </p>
        )}
      </div>

      {progress && (
        <ul className="space-y-3">
          {progress.steps.map((step) => (
            <li key={step.name} className="flex items-center gap-3">
              <StepIcon status={step.status} />
              <span
                className={`text-sm ${
                  step.status === "active"
                    ? "text-zinc-900 dark:text-zinc-100 font-medium"
                    : step.status === "completed"
                    ? "text-zinc-500 dark:text-zinc-400"
                    : "text-zinc-300 dark:text-zinc-600"
                }`}
              >
                {step.name}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
