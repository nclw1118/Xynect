"use client";

import { useEffect, useRef } from "react";
import { Bot, FileText, Paperclip, Cpu, ArrowUp } from "lucide-react";
import type { ProgressResponse, ProgressStep } from "@/lib/types";

interface Props {
  progress: ProgressResponse | null;
  isPolling: boolean;
}

// ── Step row inside the agent message card ───────────────────────────────────

function StepRow({ step }: { step: ProgressStep }) {
  if (step.status === "completed") {
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-[8px] font-bold">
          ✓
        </span>
        <span className="text-[11px] text-zinc-500 dark:text-zinc-400">{step.name}</span>
      </div>
    );
  }
  if (step.status === "active") {
    return (
      <div className="flex items-start gap-2 py-1">
        <span className="flex h-3.5 w-3.5 shrink-0 mt-0.5 rounded-full border-2 border-blue-400 dark:border-blue-500 border-t-transparent animate-spin" />
        <div>
          <span className="text-[11px] font-medium text-blue-700 dark:text-blue-300">{step.name}</span>
          <span className="ml-1.5 text-[10px] text-blue-500 dark:text-blue-400">working…</span>
        </div>
      </div>
    );
  }
  if (step.status === "error") {
    return (
      <div className="flex items-center gap-2 py-0.5">
        <span className="flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30 text-red-500 text-[8px] font-bold">
          ✕
        </span>
        <span className="text-[11px] text-red-500 dark:text-red-400">{step.name}</span>
      </div>
    );
  }
  // pending
  return (
    <div className="flex items-center gap-2 py-0.5 opacity-30">
      <span className="flex h-3.5 w-3.5 shrink-0 rounded-full border border-zinc-300 dark:border-zinc-600" />
      <span className="text-[11px] text-zinc-400 dark:text-zinc-600">{step.name}</span>
    </div>
  );
}

// ── Chat message wrappers ─────────────────────────────────────────────────────

function AssistantMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="flex h-6 w-6 shrink-0 mt-0.5 items-center justify-center rounded-full bg-zinc-900 dark:bg-zinc-100">
        <Bot className="w-3 h-3 text-white dark:text-zinc-900" />
      </div>
      <div className="flex-1 min-w-0">
        {children}
      </div>
    </div>
  );
}

function UserMessage({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex justify-end">
      {children}
    </div>
  );
}

// ── Composer (bottom, fully disabled) ────────────────────────────────────────

function Composer() {
  return (
    <div className="px-3 pb-3 pt-2 border-t border-zinc-200 dark:border-zinc-800">
      <div className="rounded-2xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800/60 overflow-hidden">
        {/* Disabled textarea */}
        <div className="px-4 pt-3 pb-2 cursor-not-allowed">
          <p className="text-[11px] text-zinc-400 dark:text-zinc-500 select-none leading-relaxed min-h-[36px]">
            Message Xynect Agent — Coming Soon
          </p>
        </div>

        {/* Composer footer */}
        <div className="flex items-center gap-1.5 px-3 pb-2.5">
          {/* Attach */}
          <button
            disabled
            title="Upload Files — Coming Soon"
            className="flex items-center justify-center w-7 h-7 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-700 text-zinc-400 cursor-not-allowed opacity-50"
          >
            <Paperclip className="w-3.5 h-3.5" />
          </button>

          {/* Model selector pill */}
          <button
            disabled
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-zinc-200 dark:border-zinc-700 text-[10px] text-zinc-400 dark:text-zinc-500 cursor-not-allowed opacity-50 select-none"
          >
            <Cpu className="w-3 h-3" />
            <span>Model</span>
          </button>

          {/* Coming soon badge */}
          <span className="ml-auto text-[9px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-700/60 text-zinc-400 dark:text-zinc-500">
            Soon
          </span>

          {/* Send button */}
          <button
            disabled
            className="flex items-center justify-center w-7 h-7 rounded-lg bg-zinc-200 dark:bg-zinc-700 text-zinc-400 cursor-not-allowed opacity-50"
          >
            <ArrowUp className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function AgentPanel({ progress, isPolling }: Props) {
  const conversationRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = conversationRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [progress?.steps.length, isPolling]);

  const completedCount = progress?.steps.filter((s) => s.status === "completed").length ?? 0;
  const totalCount = progress?.steps.length ?? 0;
  const isError = progress?.status === "error";
  const isDone = !isPolling && !isError && progress !== null;
  const fileName = progress?.uploaded_file_name;

  return (
    <aside className="w-[360px] shrink-0 border-r border-zinc-200 dark:border-zinc-800 h-full flex flex-col bg-white dark:bg-zinc-950">

      {/* ── Header ── */}
      <div className="flex items-center gap-3 px-4 py-3.5 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-950 shrink-0">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-zinc-900 dark:bg-zinc-100">
          <Bot className="w-4 h-4 text-white dark:text-zinc-900" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-zinc-900 dark:text-zinc-50 leading-tight">
            Xynect Agent
          </p>
          <p className="text-[10px] text-zinc-400 dark:text-zinc-500 leading-tight">
            AI Extraction Agent
          </p>
        </div>

        {/* Status pill */}
        {isPolling ? (
          <span className="shrink-0 flex items-center gap-1.5 text-[10px] font-medium px-2 py-0.5 rounded-full bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 border border-blue-200 dark:border-blue-800/60">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
            Working
          </span>
        ) : isDone ? (
          <span className="shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/50">
            Done
          </span>
        ) : progress ? (
          <span className="shrink-0 text-[10px] font-medium px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-800/50">
            Error
          </span>
        ) : null}
      </div>

      {/* ── Conversation area ── */}
      <div
        ref={conversationRef}
        className="flex-1 overflow-y-auto px-4 py-4 space-y-4 min-h-0 bg-zinc-50/60 dark:bg-zinc-900/40"
      >
        {/* Date/session separator */}
        <div className="flex items-center gap-3">
          <div className="flex-1 h-px bg-zinc-200 dark:bg-zinc-800" />
          <span className="text-[10px] text-zinc-400 dark:text-zinc-500 whitespace-nowrap">
            Session started
          </span>
          <div className="flex-1 h-px bg-zinc-200 dark:bg-zinc-800" />
        </div>

        {/* File attachment — user message */}
        {fileName && (
          <UserMessage>
            <div className="flex items-center gap-2 px-3 py-2 rounded-2xl rounded-tr-sm bg-zinc-200/70 dark:bg-zinc-700/60 max-w-[80%]">
              <FileText className="w-3.5 h-3.5 text-zinc-500 dark:text-zinc-400 shrink-0" />
              <span className="text-[11px] text-zinc-700 dark:text-zinc-300 font-medium truncate">
                {fileName}
              </span>
            </div>
          </UserMessage>
        )}

        {/* Agent progress message */}
        {progress && (
          <AssistantMessage>
            <div className="rounded-2xl rounded-tl-sm bg-white dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700/60 px-4 py-3 space-y-2.5 shadow-sm">
              {/* Message header */}
              <p className="text-[11px] font-medium text-zinc-600 dark:text-zinc-300 leading-snug">
                {isPolling
                  ? "I'm analyzing your file and extracting the schedule information."
                  : isDone
                  ? "Here's what was completed:"
                  : "Extraction encountered an issue:"}
              </p>

              {/* Step log */}
              {progress.steps.length > 0 && (
                <div className="border-t border-zinc-100 dark:border-zinc-700/50 pt-2 space-y-0">
                  {progress.steps.map((step) => (
                    <StepRow key={step.name} step={step} />
                  ))}
                </div>
              )}

              {/* Footer: step count */}
              {totalCount > 0 && (
                <p className="text-[10px] text-zinc-400 dark:text-zinc-500 pt-1 border-t border-zinc-100 dark:border-zinc-700/50">
                  {completedCount} / {totalCount} steps completed
                </p>
              )}
            </div>
          </AssistantMessage>
        )}

        {/* Connecting state */}
        {!progress && (
          <AssistantMessage>
            <div className="rounded-2xl rounded-tl-sm bg-white dark:bg-zinc-800/80 border border-zinc-200 dark:border-zinc-700/60 px-4 py-3">
              <p className="text-[11px] text-zinc-400 animate-pulse">Connecting…</p>
            </div>
          </AssistantMessage>
        )}

        {/* Final completion message */}
        {isDone && (
          <AssistantMessage>
            <div className="rounded-2xl rounded-tl-sm bg-emerald-50 dark:bg-emerald-900/15 border border-emerald-200 dark:border-emerald-800/40 px-4 py-3 shadow-sm">
              <p className="text-[11px] text-emerald-800 dark:text-emerald-300 leading-relaxed">
                The extraction of schedule is completed. Please see the tabs on the right for{" "}
                <span className="font-semibold">TAKE OFF</span> and{" "}
                <span className="font-semibold">QUOTE</span>.
              </p>
            </div>
          </AssistantMessage>
        )}

        {/* Error message */}
        {isError && (
          <AssistantMessage>
            <div className="rounded-2xl rounded-tl-sm bg-red-50 dark:bg-red-900/15 border border-red-200 dark:border-red-800/40 px-4 py-3">
              <p className="text-[11px] text-red-700 dark:text-red-300 leading-relaxed">
                I wasn't able to extract data from this file. Please try uploading a different file with a visible window schedule.
              </p>
            </div>
          </AssistantMessage>
        )}
      </div>

      {/* ── Composer (disabled, Coming Soon) ── */}
      <Composer />

    </aside>
  );
}
