# nadlan-genie — Product Requirements Document (PRD)

**Iteration:** 1
**Status:** Draft
**Owner:** systems-analyst (project-manager)
**Last updated:** 2026-05-17

---

## 1. Vision

`nadlan-genie` is a local-first web application that helps an individual buyer/investor spot
**potentially underpriced residential properties for sale in Israel** by comparing live listings
against locally stored Israeli transaction (sales) data and surfacing the deals whose asking price
is materially below an estimated market value.

The user runs it on their own machine via `docker compose up --build`. There is no cloud, no
background crawler, no LLM, no paid API. Every scan is initiated explicitly by the user, runs in
under a minute, and returns at most a few dozen ranked results.

---

## 2. Target user

A single technical or semi-technical real-estate buyer/investor in Israel who:

- Has Docker installed locally.
- Wants to spot deals **before** they hit broker shortlists.
- Is comfortable interpreting a ranked list of listings with a discount % and confidence score.
- Does NOT want to share their searches or data with any third party.

**Out of scope users (MVP):** brokers running concurrent scans for many clients, mobile users,
buyers outside Israel, commercial-property hunters, renters.

---

## 3. Problem statement

Israeli residential listings sites publish many properties but **do not show** an objective
estimate of market value. The buyer must mentally compare each listing against transaction history
("nadlan" data) — a slow, error-prone, expensive habit. Existing valuation services are either
paid, broker-only, or use opaque scoring.

`nadlan-genie` automates the comparable-sales lookup deterministically against open Israeli
transaction data, so the buyer immediately sees which listings deserve a deeper look.

---

## 4. Constraints (hard requirements)

| # | Constraint | Rationale |
|---|-----------|-----------|
| C1 | Local-first. Everything runs on the user's machine via `docker compose up --build`. | Zero ops cost, full data privacy. |
| C2 | No LLM, no embeddings, no vector DB. | Cost and determinism. |
| C3 | No paid APIs. | Cost. |
| C4 | No cloud dependency at runtime. | Privacy + offline-friendly. |
| C5 | No background workers / crawlers / cron. Scans are on-demand only. | Politeness + simplicity. |
| C6 | Israel-only. Residential-for-sale only. | MVP focus. |
| C7 | One city per scan, one listing source, max 3 pages, max ~50 listings, target 10–60s runtime. | Politeness + UX latency. |
| C8 | Postgres + PostGIS for storage. | Required by brief; needed for radius queries. |
| C9 | Python (FastAPI) backend, Next.js + Tailwind frontend. | Required by brief. |
| C10 | No anti-bot bypass. Respect `robots.txt`, low request volume, sane caching. | Legal + ethical. |
| C11 | Valuation logic is deterministic. No AI/ML. | Trustability + reproducibility. |

---

## 5. Listing source (MVP)

**Decision:** The MVP ships with a **single pluggable listing adapter**. Because Yad2 / Madlan
actively block automated traffic and the brief forbids anti-bot bypass, the MVP defaults to a
**file-backed `SampleAdapter`** that reads a bundled JSON fixture of ~60 sample Israeli listings
(synthesised from public transaction data for development).

The architecture exposes an `ListingAdapter` interface, and a **`Yad2Adapter` stub** is included
that uses Playwright with respectful rate limiting (1 request / 3 s, max 3 pages). It is
**disabled by default**; the user can enable it by setting `LISTING_SOURCE=yad2` in `.env` and
accepts the risk of being blocked. Documentation explains the trade-off.

This satisfies C7 and C10 while leaving a clean extension path for Madlan / broker sites.

**Assumption:** The user accepts that the default sample adapter is for demonstration and that
enabling a real adapter is at their own risk. This is documented in the README.

---

## 6. Transaction data

Source: **Israel Ministry of Finance "nadlan.gov.il" public CSV / XML transaction data**, imported
once via `POST /import-transactions` (multipart upload of a CSV or a path to a bundled file in the
container).

- Schema is normalised to a `transactions` table with PostGIS `geom` column.
- A **bundled sample CSV** of ~5,000 transactions across Tel Aviv, Ramat Gan, Haifa and Jerusalem
  is shipped under `backend/data/sample_transactions.csv` so the app is functional out-of-the-box.
- Re-importing is idempotent (UPSERT on `(deal_id, deal_date)`).

**Assumption:** The Ministry's open data licence permits redistribution of derived samples. The
README links to the source and instructs users to download a current full file for production use.

---

## 7. User stories

### US-1 — First-run setup
> As a new user, I want to `docker compose up --build`, open `http://localhost:3000`, and see a
> working dashboard with the sample data pre-loaded, so I can try the product in under 2 minutes.

**Acceptance**
- `docker compose up --build` succeeds on a clean machine.
- Backend boots, runs migrations, imports the bundled `sample_transactions.csv` if the
  `transactions` table is empty.
- Frontend loads at `http://localhost:3000` and renders the scan form.

### US-2 — Run an on-demand scan
> As a user, I want to pick a city, set rooms / max price / discount threshold / max pages, click
> "Scan Now", and see ranked results within 60 s.

**Acceptance**
- Form fields: `city` (dropdown of supported cities), `rooms_min`, `rooms_max`, `price_max`,
  `discount_threshold` (default 0.15), `max_pages` (default 3, max 3).
- Click "Scan Now" → POST `/scan` returns a `scan_id` immediately, frontend polls
  `GET /scan/{id}` every 1 s.
- Scan completes within 60 s (with sample adapter: <10 s).
- Loading state shows "Scraping…", "Valuing…", "Ranking…" sub-steps.

### US-3 — See ranked results
> As a user, I want results sorted by discount % desc with all relevant data on one row, so I can
> triage 20+ listings in 30 s.

**Acceptance** — each result shows:
- Address / neighbourhood
- Asking price (₪)
- Sqm
- Rooms
- Asking ₪/sqm
- Estimated market ₪/sqm
- Estimated market value (₪)
- Discount % (colour-coded: ≥20% green, 10–20% amber, <10% grey, <0 red)
- Confidence score (High / Medium / Low) with comparable count tooltip
- Source URL (opens in new tab)

### US-4 — Re-import or refresh transaction data
> As a user, I want to upload a new transactions CSV to keep valuations current.

**Acceptance**
- `POST /import-transactions` accepts a multipart CSV upload **or** a `path` JSON body pointing to
  a file inside the container's `/data` volume.
- Returns a summary: `{ inserted, updated, skipped, total }`.
- Progress is visible in backend logs; the request streams the file (no full-load into RAM).

### US-5 — Inspect past scans
> As a user, I want to list the last 20 scans and re-open their results, so I can compare across
> different filters.

**Acceptance**
- `GET /results?limit=20` returns the last N `scan_runs` with their filters and result count.
- Frontend has a "History" panel listing them with timestamp + city + filters.
- Clicking a history row shows that scan's results without re-running.

### US-6 — Health check
> As an operator, I want `GET /health` to return service status and DB connectivity.

**Acceptance**
- Returns `{ status: "ok", postgres: "ok", transactions_loaded: <int> }` or HTTP 503 with details.

---

## 8. Out-of-scope (MVP)

- User accounts, authentication, multi-tenant.
- Email/SMS notifications.
- Mobile-native app.
- Continuous monitoring / saved searches with alerts.
- Map view (table-only in MVP; map is a v2 feature).
- Rental properties, commercial properties, land plots.
- Cities outside Tel Aviv, Ramat Gan, Haifa, Jerusalem in the bundled sample (the schema supports
  any Israeli city; the *data* is the limit).
- Multi-source aggregation in a single scan.
- Recommendation engine / "you might also like".

---

## 9. Valuation logic (deterministic spec)

For each scraped listing `L` with sqm `s`, rooms `r`, geom `g`, property type `t`:

1. **Candidate comparables** = `transactions` rooms within `[r-1, r+1]`, property_type = `t`,
   sqm within `[0.8s, 1.2s]`, `deal_date >= now - 18 months`.
2. **Geographic filter** in widening radii:
   - First try 500 m. If ≥10 comparables → set `confidence = "high"`.
   - Else try 1 km. If ≥5 comparables → set `confidence = "medium"`.
   - Else try 2 km. If ≥3 comparables → set `confidence = "low"`.
   - Else → return `confidence = "insufficient"`, no estimate. Listing is **excluded from
     ranked results** but shown in a separate "skipped" section with reason.
3. **Median price per sqm** = median over selected comparables of `(deal_price / deal_sqm)`.
4. **Estimated value** = `median_ppsqm * s`.
5. **Discount %** = `(estimated_value - asking_price) / estimated_value`.
6. **Include in results** iff `discount_percent >= discount_threshold` AND
   `confidence != "insufficient"`.
7. Sort by `discount_percent` desc.

**Edge cases**
- Missing sqm or rooms → exclude listing, log warning.
- Estimated value ≤ 0 or asking_price ≤ 0 → exclude.
- Outlier guard: drop comparables in the top/bottom 5% of `₪/sqm` before taking the median.

---

## 10. API contract (summary)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Liveness + DB + data-loaded check |
| POST | `/scan` | Start a new scan; returns `{ scan_id, status: "queued" }` |
| GET | `/scan/{id}` | Poll status: `queued` / `running` / `done` / `error` + step + results when done |
| GET | `/results?limit=N` | List recent scans with summary |
| POST | `/import-transactions` | Bulk-import transactions (multipart CSV or `{path}` JSON) |

Full schemas live in `docs/architecture.md` and are mirrored as Pydantic models in
`backend/app/schemas.py`.

---

## 11. Database tables (summary)

- `transactions` — Israeli sales (id, deal_id, deal_date, city, neighborhood, street,
  property_type, rooms, sqm, price, geom POINT 4326).
- `listings` — scraped listings, normalised (id, source, source_listing_id, city, address,
  rooms, sqm, price, property_type, url, raw_json, geom POINT 4326, scraped_at).
- `scan_runs` — one row per scan (id, requested_at, finished_at, status, filters_json,
  step, error_msg, result_count).
- `scan_results` — N rows per scan (scan_id, listing_id, estimated_value,
  asking_price, discount_percent, median_ppsqm, comparable_count, confidence, rank).

Indexes:
- `transactions.geom` GIST
- `transactions(city, rooms, deal_date)`
- `listings.geom` GIST
- `scan_results(scan_id, rank)`

---

## 12. Non-functional requirements

| ID | Requirement |
|----|-------------|
| NFR-1 | Scan completes within 60 s on a developer laptop (M-series Mac or modern x86). |
| NFR-2 | `docker compose up --build` boots all services in under 90 s on a warm machine. |
| NFR-3 | Postgres data persists across `docker compose down` (named volume). |
| NFR-4 | No secrets in source. All configuration via `.env` / environment variables. |
| NFR-5 | Backend has a `pytest` test suite ≥70% coverage on `valuation/` and `scrape/normalize`. |
| NFR-6 | Frontend builds with no TypeScript errors; passes `next lint`. |
| NFR-7 | Logs are structured (JSON to stdout) and include `scan_id` correlation. |
| NFR-8 | Listing scraper respects 1 req / 3 s per host and stops at 3 pages. |
| NFR-9 | All user-supplied strings are validated (city allow-list, numeric bounds) at the API edge. |

---

## 13. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| Listing source blocks scraping. | Default to bundled sample adapter; mark Yad2 adapter experimental; document risk. |
| Transaction data is stale or missing for a city. | Show "insufficient data" with comparable counts; ship sample CSV for 4 major cities. |
| Median-based valuation underestimates premium streets. | Document limitation; confidence score reflects sample size; v2 adds neighbourhood-tier adjustment. |
| Docker stack heavy for casual users. | Provide one-command boot and pre-seeded data. |
| User runs many scans rapidly → scraping ban. | Backend enforces global rate limit: max 1 scan in-flight + 1 queued per process. |

---

## 14. Success metrics (for the user, not the project)

- Time from "I want to scan Ramat Gan" → seeing ranked results: **< 60 s**.
- A typical scan returns **5–20** listings with `discount % >= 15%` on the sample data set.
- Zero crashes on the 10 acceptance scans defined in the QA plan.

---

## 15. Open assumptions (resolved by PM, not asking user)

1. Single-user, no auth — confirmed by "local-first".
2. Default discount threshold 0.15 (15%) — middle of typical investor heuristics.
3. Sample data set covers Tel Aviv, Ramat Gan, Haifa, Jerusalem — top-4 by transaction volume.
4. Default listing adapter is `sample` — only way to satisfy "no anti-bot bypass" + "deliver a
   working demo".
5. Currency is **NIS (₪)** throughout, no FX.
6. Property types in MVP: `apartment`, `garden_apartment`, `penthouse`, `private_house`. Filter
   defaults to `apartment`.
7. Frontend language: **English UI for MVP** (Hebrew RTL is a v2 enhancement). Addresses display
   in original Hebrew when available.

These are recorded so future iterations can override them explicitly.
