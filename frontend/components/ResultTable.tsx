"use client";

import type { ScanResultOut } from "@/lib/types";
import {
  confidenceBadge,
  discountColor,
  formatInt,
  formatNis,
  formatPercent,
} from "@/lib/format";

export function ResultTable({ results }: { results: ScanResultOut[] }) {
  if (!results.length) {
    return (
      <div className="rounded border border-dashed border-slate-300 bg-white p-6 text-center text-sm text-slate-500">
        No listings beat the discount threshold. Try lowering it or widening rooms.
      </div>
    );
  }
  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="px-3 py-2 text-left font-medium">Disc%</th>
            <th className="px-3 py-2 text-right font-medium">Asking</th>
            <th className="px-3 py-2 text-right font-medium">Est. value</th>
            <th className="px-3 py-2 text-right font-medium">₪/sqm</th>
            <th className="px-3 py-2 text-right font-medium">Est ₪/sqm</th>
            <th className="px-3 py-2 text-right font-medium">Sqm</th>
            <th className="px-3 py-2 text-right font-medium">R</th>
            <th className="px-3 py-2 text-left font-medium">Conf</th>
            <th className="px-3 py-2 text-left font-medium">Listing</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {results.map((r) => {
            const askPpSqm =
              r.listing.sqm && r.listing.price
                ? r.listing.price / r.listing.sqm
                : null;
            return (
              <tr key={r.rank} className="hover:bg-slate-50">
                <td
                  className={`px-3 py-2 text-left font-bold tabular-nums ${discountColor(
                    r.discount_percent,
                  )}`}
                  title={`${(r.discount_percent * 100).toFixed(2)}%`}
                >
                  {formatPercent(r.discount_percent, 0)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums" title={String(r.asking_price)}>
                  {formatNis(r.asking_price)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums" title={String(r.estimated_value)}>
                  {formatNis(r.estimated_value)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatInt(askPpSqm)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums text-slate-500">
                  {formatInt(r.median_ppsqm)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {formatInt(r.listing.sqm)}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {r.listing.rooms ?? "—"}
                </td>
                <td className="px-3 py-2 text-left">
                  <span
                    className={`rounded px-2 py-0.5 text-xs font-medium uppercase ${confidenceBadge(
                      r.confidence,
                    )}`}
                    title={`${r.comparable_count} comparables within ${r.radius_m} m`}
                    aria-label={`${r.confidence} confidence`}
                  >
                    {r.confidence}
                  </span>
                </td>
                <td className="px-3 py-2 text-left">
                  <a
                    href={r.listing.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-emerald-700 hover:underline"
                  >
                    {r.listing.address ||
                      r.listing.neighborhood ||
                      r.listing.city}{" "}
                    ↗
                  </a>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
