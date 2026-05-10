import Link from "next/link";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-white dark:bg-zinc-950 px-6">
      <div className="max-w-2xl w-full text-center space-y-10">

        {/* Brand label */}
        <p className="text-xs font-mono tracking-[0.2em] text-zinc-400 uppercase">
          Xynect
        </p>

        {/* Hero heading */}
        <div className="space-y-4">
          <h1 className="text-4xl sm:text-5xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50 leading-tight">
            AI-Powered Construction<br />Material Supply Chain
          </h1>
          <p className="text-base sm:text-lg text-zinc-500 dark:text-zinc-400 max-w-lg mx-auto leading-relaxed">
            Upload your construction documents and let Xynect extract window schedules,
            project location, quantities, and key product requirements — then match them
            with supplier and pricing options.
          </p>
        </div>

        {/* Primary CTA */}
        <div className="flex flex-col items-center gap-3">
          <Link
            href="/upload"
            className={cn(buttonVariants({ size: "lg" }), "px-8 text-base")}
          >
            Upload Construction File
          </Link>
          <p className="text-xs text-zinc-400">
            PDF · JPEG · PNG · Excel · CSV &nbsp;·&nbsp; Max 75 MB &nbsp;·&nbsp; Windows only
          </p>
        </div>

      </div>
    </main>
  );
}
