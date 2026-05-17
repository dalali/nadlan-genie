# nadlan-genie — UI/UX Design

**Iteration:** 1
**Status:** Draft
**Owner:** ui-ux-designer (project-manager)
**Last updated:** 2026-05-17

---

## 1. Design principles

1. **One-page utility, not a SaaS product.** The user is here to scan, scan again, and read a
   ranked table. No marketing, no onboarding flow.
2. **Speed over polish.** The dashboard must render in <500 ms and the result table must be usable
   on a 13" laptop screen without horizontal scroll.
3. **Numbers first, decoration second.** Discount % is the most important field; it gets the
   largest type and a colour.
4. **Honest uncertainty.** Confidence is always shown with the result, never hidden.
5. **Tailwind defaults, no custom theme.** Avoid bikeshedding; ship.

---

## 2. Information architecture

```
/  (single page; no router)
├── Header: brand + version + GitHub link
├── Scan Form (left column on ≥md, top on mobile)
├── Results Panel (right column on ≥md, below on mobile)
│   ├── Status bar (idle | running | done | error)
│   ├── Result table (when done)
│   └── Skipped list (collapsed by default)
└── History panel (collapsed by default at bottom)
```

A single page, no client-side router. State held in React Context (`ScanContext`).

---

## 3. Page layout (desktop ≥1024px)

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│  nadlan-genie                                       v0.1.0    github   docs      │
├────────────────────────┬─────────────────────────────────────────────────────────┤
│  SCAN                  │  RESULTS                                                │
│ ┌────────────────────┐ │ ┌─────────────────────────────────────────────────────┐ │
│ │ City               │ │ │  Status: ● done   ·  scan_id 7a3c  ·  12 results    │ │
│ │ [Ramat Gan      ▾] │ │ │  Filters: Ramat Gan, 3-4 rms, ≤ ₪3.0M, ≥15% off    │ │
│ │                    │ │ ├─────────────────────────────────────────────────────┤ │
│ │ Rooms              │ │ │ Disc%│Asking  │ Est.   │ ₪/sqm │ Sqm │ R │ Conf │ ↗  │ │
│ │ [3 ▾] – [4 ▾]      │ │ │  22% │₪2.34M  │ ₪3.00M │ 30,000│ 78  │ 3 │ HIGH │ ↗  │ │
│ │                    │ │ │  18% │₪2.10M  │ ₪2.56M │ 28,400│ 74  │ 3 │ MED  │ ↗  │ │
│ │ Max price          │ │ │  16% │₪2.80M  │ ₪3.33M │ 32,300│ 86  │ 4 │ HIGH │ ↗  │ │
│ │ [3,000,000      ₪] │ │ │  ...                                                │ │
│ │                    │ │ ├─────────────────────────────────────────────────────┤ │
│ │ Discount threshold │ │ │ ▸ 6 listings skipped (insufficient comparables)     │ │
│ │ [ 15 % ]           │ │ └─────────────────────────────────────────────────────┘ │
│ │                    │ │                                                         │
│ │ Max pages          │ │  HISTORY (▾)                                            │
│ │ [3] (max 3)        │ │  2026-05-17 14:02  Ramat Gan  3-4r ≤3M    12 results   │
│ │                    │ │  2026-05-17 13:55  Tel Aviv   2-3r ≤2M     7 results   │
│ │ [ Scan Now ]       │ │                                                         │
│ └────────────────────┘ │                                                         │
└────────────────────────┴─────────────────────────────────────────────────────────┘
```

---

## 4. Responsive behaviour

- `< md (768px)`: form stacks above results, table becomes vertically scrolling cards.
- `md – lg`: two-column layout, table compresses columns (hides ₪/sqm, keeps disc + asking + est + sqm + rooms + conf).
- `≥ lg`: full table as drawn above.

---

## 5. Components

### 5.1 `ScanForm`

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| `city` | Select | "Tel Aviv" | one of allow-list from `/cities` |
| `rooms_min` | Select (1–7) | 3 | ≤ rooms_max |
| `rooms_max` | Select (1–7) | 4 | ≥ rooms_min |
| `price_max` | NumberInput (₪) | 3,000,000 | > 0, ≤ 50,000,000 |
| `discount_threshold` | Slider 0–50% | 15% | — |
| `max_pages` | Number | 3 | 1–3 |
| `property_type` | Select | apartment | from enum |

- Submit button is disabled while a scan is in-flight.
- Inline validation errors appear below each field.

### 5.2 `StatusBar`

States and copy:
- `idle` → "Configure filters and click Scan Now."
- `queued` → "Scan queued…" + small spinner.
- `running` → "Scraping… (step 1/4)" / "Normalising… (2/4)" / "Valuing… (3/4)" / "Ranking… (4/4)".
- `done` → green dot + "N results · scanned in Xs".
- `error` → red dot + error message + "Retry" button.

### 5.3 `ResultTable`

Columns (desktop):

| Col | Format | Sort | Notes |
|-----|--------|------|-------|
| Disc % | bold, 2-digit, colour-coded | desc default | green ≥20 / amber 10–19 / grey <10 / red <0 |
| Asking | ₪ short (₪2.34M) | yes | tooltip: full integer |
| Est. value | ₪ short | yes | tooltip: full integer |
| ₪/sqm | int | yes | listing's asking ₪/sqm |
| Est ₪/sqm | int (lighter colour) | no | the median used |
| Sqm | int | yes | |
| Rooms | half-step decimal | yes | |
| Confidence | badge HIGH/MED/LOW | no | tooltip: "N comparables within R m" |
| Source | external-link icon | no | opens listing url in new tab |

- Row hover highlights row.
- Clicking a row expands a detail panel: address, neighbourhood, comparable count, comparable
  median, comparable date range, raw scraped snippet.

### 5.4 `SkippedList`

Collapsed by default. Shows skipped listings grouped by reason:
- `insufficient_comparables` (n)
- `missing_sqm` (n)
- `discount_below_threshold` (n)

Each entry shows address + URL only.

### 5.5 `HistoryPanel`

Last 20 scans as a compact table. Click → loads that scan's results into the panel without
re-scanning.

### 5.6 `Footer` / `Header`

- Header: brand name (`nadlan-genie`), version pill, GitHub link, docs link.
- Footer: link to `/health`, "Built locally · No cloud · No tracking".

---

## 6. Colours (Tailwind)

| Token | Tailwind class | Use |
|-------|---------------|-----|
| brand | `slate-900` text on `white` bg | header |
| accent | `emerald-600` | primary action button |
| good | `emerald-600` | discount ≥20%, HIGH confidence |
| warn | `amber-500` | discount 10–19%, MED confidence |
| neutral | `slate-400` | LOW confidence, discount <10% |
| bad | `rose-500` | discount <0%, errors |
| surface | `slate-50` | card background |
| border | `slate-200` | dividers |

Dark mode: out of scope for MVP.

---

## 7. Typography

- Sans-serif system stack (Tailwind default).
- Brand: `text-2xl font-semibold tracking-tight`.
- Table body: `text-sm`.
- Discount %: `text-lg font-bold tabular-nums`.
- Numbers throughout: `tabular-nums` for alignment.

---

## 8. Empty / loading / error states

| State | Copy |
|-------|------|
| First run, no scan yet | "No scan yet. Fill the form and click Scan Now." (centered, slate-400) |
| Loading | spinner + current step |
| 0 results returned | "No listings beat the discount threshold. Try lowering it or widening rooms." |
| Adapter blocked / scrape failed | "Listing source unreachable. Check `LISTING_SOURCE` in .env or try `sample`." |
| DB empty (no transactions) | "Transaction data is empty. Run `POST /import-transactions` or restart with bundled sample." with copy-button for the curl command |
| Backend down | "Backend unreachable at /api. Is the backend container running?" |

---

## 9. Interaction details

- "Scan Now" button shows an inline spinner and disables until response. If the request returns
  `{status: "queued"|"running"}`, polling starts at 1 Hz against `GET /scan/{id}`. Poll stops on
  `done` or `error`.
- ESC closes any open detail panel.
- `Enter` inside the form submits.
- A scan in flight can be cancelled with a "Cancel" link (DELETE `/scan/{id}` — best-effort).

---

## 10. Accessibility

- All form fields have `<label>` associations.
- Buttons have focus rings (`focus-visible:outline-2 outline-emerald-600`).
- Confidence badges include `aria-label` (e.g. "high confidence").
- Discount % colour is paired with an icon (▲/▼/●) so colour-blind users can still rank.
- Tab order: city → rooms_min → rooms_max → price_max → discount → max_pages → property_type → Scan Now.

---

## 11. Frontend stack alignment

- **Next.js 14 App Router**, single `app/page.tsx`.
- **Tailwind CSS** (default config + `tabular-nums` plugin via inline styles).
- **TypeScript** strict.
- **No state library** — `useState` + `useReducer` in a small `ScanContext`.
- **API client** is a tiny `fetch` wrapper in `lib/api.ts`; base URL `process.env.NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).
- **No SSR data fetching for scans** — all calls are client-side; the page itself is statically rendered.

---

## 12. Wireframe — mobile (≤ 640px)

```
┌────────────────────────────┐
│ nadlan-genie       v0.1.0  │
├────────────────────────────┤
│ SCAN                       │
│  City   [Ramat Gan ▾]      │
│  Rooms  [3 ▾]–[4 ▾]        │
│  Max ₪  [3,000,000]        │
│  Disc   [——●——] 15%        │
│  Pages  [3]                │
│  [    Scan Now    ]        │
├────────────────────────────┤
│ ● done · 12 results · 14s  │
├────────────────────────────┤
│ ┌──────────────────────────┐│
│ │ 22% off  HIGH            ││
│ │ ₪2.34M  →  est ₪3.00M    ││
│ │ 78 sqm · 3 rms · 30k/sqm ││
│ │ Bialik 14, Ramat Gan  ↗  ││
│ └──────────────────────────┘│
│  ...                       │
└────────────────────────────┘
```

---

## 13. HTML mock — single-result card (illustrative)

```html
<article class="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
  <div class="flex items-baseline justify-between">
    <span class="text-2xl font-bold tabular-nums text-emerald-600">22%</span>
    <span class="rounded bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">HIGH</span>
  </div>
  <div class="mt-2 grid grid-cols-2 gap-y-1 text-sm tabular-nums">
    <span class="text-slate-500">Asking</span><span>₪2,340,000</span>
    <span class="text-slate-500">Est. value</span><span>₪3,000,000</span>
    <span class="text-slate-500">₪/sqm</span><span>30,000</span>
    <span class="text-slate-500">Est ₪/sqm</span><span>38,500</span>
    <span class="text-slate-500">Sqm</span><span>78</span>
    <span class="text-slate-500">Rooms</span><span>3</span>
  </div>
  <a href="https://example.com/listing/123" target="_blank" rel="noopener"
     class="mt-3 inline-flex items-center gap-1 text-sm text-emerald-700 hover:underline">
    Bialik 14, Ramat Gan ↗
  </a>
</article>
```

---

## 14. Assumptions (resolved, not asking)

- Single-language UI (English) — Hebrew RTL deferred to v2.
- No charts in MVP (one screenshot's worth of useful chart needs neighbourhood-tier data that we
  don't have yet).
- No maps in MVP (Leaflet would be ~250 KB and adds CI complexity; deferred to v2).
- Default sort = discount % desc; user can re-sort by clicking column headers (client-side only).
