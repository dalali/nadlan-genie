"use client";

import { useState } from "react";
import type { SkippedItem } from "@/lib/types";

export function SkippedList({ items }: { items: SkippedItem[] }) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  const grouped: Record<string, SkippedItem[]> = {};
  items.forEach((it) => {
    grouped[it.reason] = grouped[it.reason] || [];
    grouped[it.reason].push(it);
  });
  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-sm"
      >
        <span className="text-slate-600">
          {open ? "▾" : "▸"} {items.length} listings skipped
        </span>
        <span className="text-xs text-slate-400">click to {open ? "hide" : "show"}</span>
      </button>
      {open && (
        <div className="border-t border-slate-100 px-3 py-2">
          {Object.entries(grouped).map(([reason, list]) => (
            <div key={reason} className="mb-3">
              <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                {reason} ({list.length})
              </div>
              <ul className="space-y-1 text-xs">
                {list.slice(0, 25).map((it) => (
                  <li key={it.url}>
                    <a
                      href={it.url}
                      target="_blank"
                      rel="noopener"
                      className="text-slate-600 hover:text-slate-900 hover:underline"
                    >
                      {it.url}
                    </a>
                  </li>
                ))}
                {list.length > 25 && (
                  <li className="text-slate-400">… and {list.length - 25} more</li>
                )}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
