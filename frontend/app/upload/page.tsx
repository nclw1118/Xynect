import Link from "next/link";
import { FileDropzone } from "@/components/FileDropzone";

export const metadata = {
  title: "Upload — Xynect",
};

export default function UploadPage() {
  return (
    <main className="flex min-h-screen flex-col bg-white dark:bg-zinc-950">
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-16">
        <div className="w-full max-w-xl space-y-8">

          {/* Back link */}
          <Link
            href="/"
            className="inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300 transition-colors"
          >
            ← Back
          </Link>

          {/* Page heading */}
          <div className="space-y-2">
            <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">
              Upload Construction File
            </h1>
            <p className="text-sm text-zinc-500 dark:text-zinc-400">
              Upload a PDF, image, or spreadsheet containing a window schedule.
              Xynect will extract window data and prepare it for review.
            </p>
          </div>

          {/* Dropzone */}
          <FileDropzone />

        </div>
      </div>
    </main>
  );
}
