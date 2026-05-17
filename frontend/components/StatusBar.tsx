"use client";

import type { ScanDetail } from "@/lib/types";

const STEP_COPY: Record<string, string> = {
  scrape: "Scraping listings... (1/4)",
  normalize: "Normalising... (2/4)",
  value: "Valuing... (3/4)",
  rank: "Ranking... (4/4)",
};

export function StatusBar({ scan }: { scan: ScanDetail | null }) {
  if (!scan) {
    return (
      <div className="rounded border border-dashed border-slate-300 bg-white p-3 text-sm text-slate-500">
        Configure filters and click Scan Now.
      </div>
    );
  }
  if (scan.status === "queued" || scan.status === "running") {
    return (
      <div className="flex items-center gap-2 rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
        {scan.status === "queued"
          ? "Scan queued..."
          : STEP_COPY[scan.step || ""] || "Running..."}
      </div>
    );
  }
  if (scan.status === "error") {
    return (
      <div className="rounded border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">
        <span className="inline-block h-2 w-2 rounded-full bg-rose-500" />{" "}
        Error: {scan.error_msg || "unknown"}
      </div>
    );
  }
  // done
  return (
    <div className="flex items-center justify-between rounded border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
      <div className="flex items-center gap-2">
        <span className="inline-block h-2 w-2 rounded-full bg-emerald-500" />
        {scan.result_count ?? 0} result(s)
      </div>
      <div className="text-xs text-emerald-700/80 tabular-nums">
        scan {scan.scan_id.slice(0, 8)}
      </div>
    </div>
  );
}
