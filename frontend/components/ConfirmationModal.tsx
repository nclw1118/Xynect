"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { apiFetch } from "@/lib/api";
import type { ConfirmResponse } from "@/lib/types";

interface Props {
  sessionId: string;
  onClose: () => void;
  onConfirmed: (next: string) => void;
}

export function ConfirmationModal({ sessionId, onClose, onConfirmed }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleConfirm = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<ConfirmResponse>(
        `/api/sessions/${sessionId}/confirm`,
        { method: "POST" }
      );
      onConfirmed(res.next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Confirm failed.");
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 dark:bg-black/60"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative z-10 bg-white dark:bg-zinc-900 rounded-2xl shadow-2xl max-w-md w-full p-6 space-y-5">
        <div className="space-y-2">
          <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
            Confirm extracted data
          </h2>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
            Are you done reviewing the extracted window information?
          </p>
          <p className="text-sm text-zinc-500 dark:text-zinc-400 leading-relaxed">
            You can still go back and make changes. Once confirmed, Xynect will use
            this information to generate supplier and pricing recommendations.
          </p>
        </div>

        {error && (
          <p className="text-sm text-red-600 dark:text-red-400">{error}</p>
        )}

        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={onClose} disabled={loading}>
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={loading}>
            {loading ? "Generating…" : "All Good"}
          </Button>
        </div>
      </div>
    </div>
  );
}
