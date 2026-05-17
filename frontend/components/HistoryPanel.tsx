"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { ScanListItem } from "@/lib/types";

interface Props {
  onSelect: (scanId: string) => void;
  refreshKey: number;
}

export function HistoryPanel({ onSelect, refreshKey }: Props) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ScanListItem[]>([]);

  useEffect(() => {
    let cancelled = false;
    api
      .listScans(20)
      .then((d) => {
        if (!cancelled) setItems(d.scans);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [refreshKey]);

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
      >
        <span className="text-slate-700">
          {open ? "▾" : "▸"} History ({items.length})
        </span>
        <span className="text-xs text-slate-400">click to {open ? "hide" : "show"}</span>
      </button>
      {open && (
        <table className="w-full border-t border-slate-100 text-xs">
          <tbody>
            {items.map((it) => (
              <tr
                key={it.scan_id}
                className="cursor-pointer hover:bg-slate-50"
                onClick={() => onSelect(it.scan_id)}
              >
                <td className="px-3 py-1 tabular-nums text-slate-600">
                  {new Date(it.requested_at).toLocaleString()}
                </td>
                <td className="px-3 py-1">{it.city}</td>
                <td className="px-3 py-1 tabular-nums">
                  {String(it.filters.rooms_min)}-{String(it.filters.rooms_max)}r ≤ ₪
                  {Number(it.filters.price_max).toLocaleString()}
                </td>
                <td className="px-3 py-1 text-right tabular-nums">
                  {it.result_count ?? "—"}
                </td>
                <td className="px-3 py-1 text-right uppercase text-slate-500">
                  {it.status}
                </td>
              </tr>
            ))}
            {!items.length && (
              <tr>
                <td className="px-3 py-2 text-slate-400">No prior scans.</td>
              </tr>
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
