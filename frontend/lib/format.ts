export function formatNis(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1_000_000) return `₪${(n / 1_000_000).toFixed(2)}M`;
  if (Math.abs(n) >= 1_000) return `₪${(n / 1_000).toFixed(0)}K`;
  return `₪${n.toFixed(0)}`;
}

export function formatInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return Math.round(n).toLocaleString("en-US");
}

export function formatPercent(p: number | null | undefined, digits = 0): string {
  if (p === null || p === undefined || Number.isNaN(p)) return "—";
  return `${(p * 100).toFixed(digits)}%`;
}

export function discountColor(p: number): string {
  if (p < 0) return "text-rose-600";
  if (p >= 0.2) return "text-emerald-600";
  if (p >= 0.1) return "text-amber-600";
  return "text-slate-500";
}

export function confidenceBadge(conf: string): string {
  switch (conf) {
    case "high":
      return "bg-emerald-50 text-emerald-700";
    case "medium":
      return "bg-amber-50 text-amber-700";
    case "low":
      return "bg-slate-100 text-slate-600";
    default:
      return "bg-slate-100 text-slate-600";
  }
}
