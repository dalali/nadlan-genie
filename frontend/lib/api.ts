import type {
  HealthOut,
  ScanDetail,
  ScanListItem,
  ScanRequest,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    cache: "no-store",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export const api = {
  health: () => request<HealthOut>("/health"),
  cities: () => request<{ cities: string[] }>("/cities"),
  createScan: (req: ScanRequest) =>
    request<{ scan_id: string; status: string }>("/scan", {
      method: "POST",
      body: JSON.stringify(req),
    }),
  getScan: (id: string) => request<ScanDetail>(`/scan/${id}`),
  cancelScan: (id: string) =>
    request<{ status: string }>(`/scan/${id}`, { method: "DELETE" }),
  listScans: (limit = 20) =>
    request<{ scans: ScanListItem[] }>(`/results?limit=${limit}`),
};
