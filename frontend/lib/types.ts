export type ScanStatus = "queued" | "running" | "done" | "error";
export type ScanStep = "scrape" | "normalize" | "value" | "rank";
export type Confidence = "high" | "medium" | "low";

export interface ScanRequest {
  city: string;
  rooms_min: number;
  rooms_max: number;
  price_max: number;
  discount_threshold: number;
  max_pages: number;
  property_type: "apartment" | "garden_apartment" | "penthouse" | "private_house";
}

export interface ListingOut {
  id: number;
  url: string;
  address: string | null;
  neighborhood: string | null;
  city: string;
  rooms: number | null;
  sqm: number | null;
  price: number | null;
  property_type: string | null;
}

export interface ScanResultOut {
  rank: number;
  listing: ListingOut;
  asking_price: number;
  estimated_value: number;
  median_ppsqm: number;
  discount_percent: number;
  comparable_count: number;
  radius_m: number;
  confidence: Confidence;
}

export interface SkippedItem {
  url: string;
  reason: string;
}

export interface ScanDetail {
  scan_id: string;
  status: ScanStatus;
  step?: ScanStep | null;
  filters: Record<string, unknown>;
  requested_at: string;
  finished_at: string | null;
  result_count: number | null;
  error_msg?: string | null;
  results: ScanResultOut[];
  skipped: SkippedItem[];
}

export interface ScanListItem {
  scan_id: string;
  requested_at: string;
  finished_at: string | null;
  status: ScanStatus;
  city: string;
  filters: Record<string, unknown>;
  result_count: number | null;
}

export interface HealthOut {
  status: string;
  postgres: string;
  transactions_loaded: number;
  version: string;
}
