# nadlan-genie — Architecture

**Iteration:** 1
**Status:** Draft
**Owner:** systems-architect (project-manager)
**Last updated:** 2026-05-17

---

## 1. High-level shape

```
┌──────────────────┐        HTTP            ┌──────────────────────┐
│  Browser (Next)  │ ─────────────────────► │  FastAPI backend     │
│  http://3000     │   /api/* (proxied)     │  http://8000         │
└──────────────────┘                        └──────────┬───────────┘
                                                       │
                                                       │ SQLAlchemy
                                                       ▼
                                            ┌──────────────────────┐
                                            │  Postgres + PostGIS  │
                                            │  port 5432 (in net)  │
                                            └──────────────────────┘

   ↑ Listing source (Playwright / requests)
   │
   └── invoked synchronously per scan; not a separate service
```

Three Docker Compose services: `postgres`, `backend`, `frontend`. One private network
(`nadlan_net`), one named volume (`pgdata`), no external ports beyond 3000 (frontend) and 8000
(backend) on localhost.

---

## 2. Tech stack decisions

| Layer | Choice | Reason |
|-------|--------|--------|
| Backend framework | **FastAPI** | Pydantic models, async ready, OpenAPI built-in. |
| ORM | **SQLAlchemy 2.0** | Mature, async-friendly, GIS dialect via `geoalchemy2`. |
| GIS bindings | **geoalchemy2** + `shapely` | Standard for PostGIS in Python. |
| Migrations | **Alembic** | Standard with SQLAlchemy. Two migrations: `0001_init`, plus seed loader script. |
| Scraping | **Playwright (async, Chromium)** for `yad2` adapter (gated); **`requests` + `BeautifulSoup`** for the simple HTML mock used by integration tests. Default `sample` adapter reads JSON file. | Brief allows either; default sample = zero browser. |
| Frontend | **Next.js 14 App Router** + **Tailwind v3** + **TypeScript** | Brief; matches design doc. |
| HTTP client (FE) | `fetch` wrapper, no axios | Smaller bundle. |
| Tests (BE) | **pytest** + `httpx.AsyncClient` + `pytest-asyncio` | Standard. |
| Tests (FE) | **vitest** + React Testing Library (smoke only) | Lightweight. |
| Containerisation | **Docker Compose** | Brief. |
| DB | **postgis/postgis:16-3.4** | Brief. |
| Process model | Backend runs **uvicorn** single worker (sufficient for local). Scans run in a background `asyncio.Task`; status persisted to DB so polling works across requests. | No external queue needed. |
| Logging | **structlog** → JSON stdout | NFR-7. |

---

## 3. Repository layout

```
nadlan-genie/
├── README.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── docs/
│   ├── PRD.md
│   ├── design.md
│   └── architecture.md
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml          # or requirements.txt for simplicity
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 0001_init.py
│   ├── data/
│   │   ├── sample_transactions.csv
│   │   └── sample_listings.json
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app + lifespan
│   │   ├── config.py           # pydantic-settings
│   │   ├── db.py               # engine, session, base
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── schemas.py          # Pydantic models (API contracts)
│   │   ├── deps.py             # FastAPI dependencies
│   │   ├── logging_setup.py
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── health.py
│   │   │   ├── scan.py
│   │   │   ├── results.py
│   │   │   ├── transactions.py
│   │   │   └── cities.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── scan_runner.py  # orchestrates a scan
│   │   │   ├── valuation.py    # deterministic valuation
│   │   │   └── importer.py     # CSV → transactions
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # ListingAdapter ABC
│   │   │   ├── sample.py       # reads sample_listings.json
│   │   │   └── yad2.py         # Playwright stub (disabled by default)
│   │   ├── geo.py              # geocoding helpers (city centroid lookup)
│   │   └── seed.py             # on-startup seeding logic
│   └── tests/
│       ├── conftest.py
│       ├── test_health.py
│       ├── test_valuation.py
│       ├── test_importer.py
│       ├── test_scan_flow.py
│       └── test_adapters.py
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── tsconfig.json
    ├── tailwind.config.ts
    ├── postcss.config.js
    ├── next.config.mjs
    ├── app/
    │   ├── layout.tsx
    │   ├── page.tsx
    │   └── globals.css
    ├── components/
    │   ├── ScanForm.tsx
    │   ├── StatusBar.tsx
    │   ├── ResultTable.tsx
    │   ├── SkippedList.tsx
    │   ├── HistoryPanel.tsx
    │   └── Header.tsx
    ├── lib/
    │   ├── api.ts
    │   ├── format.ts
    │   └── types.ts
    └── tests/
        └── ScanForm.test.tsx
```

---

## 4. Data model (DDL summary)

```sql
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE transactions (
    id              BIGSERIAL PRIMARY KEY,
    deal_id         TEXT NOT NULL,
    deal_date       DATE NOT NULL,
    city            TEXT NOT NULL,
    neighborhood    TEXT,
    street          TEXT,
    house_number    TEXT,
    property_type   TEXT NOT NULL,        -- 'apartment'|'garden_apartment'|'penthouse'|'private_house'
    rooms           NUMERIC(3,1),
    sqm             NUMERIC(7,2),
    price           NUMERIC(12,0) NOT NULL,
    geom            GEOMETRY(Point, 4326) NOT NULL,
    UNIQUE (deal_id, deal_date)
);
CREATE INDEX transactions_geom_gix ON transactions USING GIST (geom);
CREATE INDEX transactions_city_rooms_date_idx ON transactions (city, rooms, deal_date);

CREATE TABLE listings (
    id                  BIGSERIAL PRIMARY KEY,
    source              TEXT NOT NULL,
    source_listing_id   TEXT NOT NULL,
    city                TEXT NOT NULL,
    neighborhood        TEXT,
    address             TEXT,
    rooms               NUMERIC(3,1),
    sqm                 NUMERIC(7,2),
    price               NUMERIC(12,0),
    property_type       TEXT,
    url                 TEXT NOT NULL,
    raw_json            JSONB,
    geom                GEOMETRY(Point, 4326),
    scraped_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, source_listing_id)
);
CREATE INDEX listings_geom_gix ON listings USING GIST (geom);

CREATE TABLE scan_runs (
    id              UUID PRIMARY KEY,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at     TIMESTAMPTZ,
    status          TEXT NOT NULL,        -- queued|running|done|error
    step            TEXT,                 -- scrape|normalize|value|rank
    error_msg       TEXT,
    filters_json    JSONB NOT NULL,
    result_count    INT
);

CREATE TABLE scan_results (
    scan_id             UUID NOT NULL REFERENCES scan_runs(id) ON DELETE CASCADE,
    rank                INT NOT NULL,
    listing_id          BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    asking_price        NUMERIC(12,0) NOT NULL,
    estimated_value     NUMERIC(12,0) NOT NULL,
    median_ppsqm        NUMERIC(10,2) NOT NULL,
    discount_percent    NUMERIC(5,4) NOT NULL,
    comparable_count    INT NOT NULL,
    radius_m            INT NOT NULL,
    confidence          TEXT NOT NULL,    -- high|medium|low
    PRIMARY KEY (scan_id, rank)
);
CREATE INDEX scan_results_scan_idx ON scan_results (scan_id);
```

---

## 5. API contracts (full)

All requests/responses are JSON. CORS is enabled for `http://localhost:3000`.

### `GET /health`
```json
200 OK
{
  "status": "ok",
  "postgres": "ok",
  "transactions_loaded": 5012,
  "version": "0.1.0"
}
```
503 if DB unreachable.

### `GET /cities`
```json
200 OK
{ "cities": ["Tel Aviv", "Ramat Gan", "Haifa", "Jerusalem"] }
```
Derived from `SELECT DISTINCT city FROM transactions ORDER BY city`.

### `POST /scan`
Request:
```json
{
  "city": "Ramat Gan",
  "rooms_min": 3,
  "rooms_max": 4,
  "price_max": 3000000,
  "discount_threshold": 0.15,
  "max_pages": 3,
  "property_type": "apartment"
}
```
Response:
```json
202 Accepted
{ "scan_id": "7a3c…", "status": "queued" }
```
Validation: city ∈ `/cities`; numeric bounds; `max_pages ≤ 3`.

### `GET /scan/{id}`
Response while running:
```json
{ "scan_id": "...", "status": "running", "step": "value" }
```
Response when done:
```json
{
  "scan_id": "...",
  "status": "done",
  "filters": { ... },
  "requested_at": "...",
  "finished_at": "...",
  "result_count": 12,
  "results": [
    {
      "rank": 1,
      "listing": {
        "url": "...", "address": "Bialik 14", "neighborhood": "Marom Naveh",
        "city": "Ramat Gan", "rooms": 3, "sqm": 78, "price": 2340000,
        "property_type": "apartment"
      },
      "asking_price": 2340000,
      "estimated_value": 3000000,
      "median_ppsqm": 38461.5,
      "discount_percent": 0.22,
      "comparable_count": 14,
      "radius_m": 500,
      "confidence": "high"
    },
    ...
  ],
  "skipped": [
    { "url": "...", "reason": "insufficient_comparables" },
    ...
  ]
}
```

### `DELETE /scan/{id}`
Best-effort cancellation. Sets status to `error` with `error_msg: "cancelled"`.

### `GET /results?limit=20`
List recent scans (no full results, for history panel).
```json
{
  "scans": [
    { "scan_id": "...", "requested_at": "...", "finished_at": "...",
      "city": "Ramat Gan", "filters": {...}, "result_count": 12, "status": "done" }
  ]
}
```

### `POST /import-transactions`
Two modes:
- **multipart**: `Content-Type: multipart/form-data` with field `file`.
- **JSON**: `{ "path": "/data/sample_transactions.csv" }` (path inside container).

Response:
```json
{ "inserted": 4500, "updated": 12, "skipped": 30, "total": 4542 }
```

---

## 6. Scan runtime flow

```
POST /scan
   │
   ▼
[validate filters] ── 400 on bad input
   │
   ▼
[insert scan_runs row, status="queued"]
   │
   ▼
[spawn asyncio.create_task(run_scan(scan_id))]
   │
   ▼  202 Accepted {scan_id}

  run_scan(scan_id):
     update step = "scrape"
     listings_raw = await adapter.search(city, rooms_min, rooms_max, price_max, max_pages, property_type)
     update step = "normalize"
     listings = normalize(listings_raw)  # geocode missing coords using city centroid + offset
     upsert listings to DB
     update step = "value"
     for each listing:
        v = value(listing)  # see §7
     update step = "rank"
     filter by discount_threshold; sort by discount desc; insert into scan_results
     update status = "done", finished_at = now()
```

A global `asyncio.Semaphore(1)` ensures only one scan runs at a time per process (NFR-8 +
politeness).

---

## 7. Valuation algorithm (Python pseudocode)

```python
def value(listing, db):
    # Step 1: candidate base filter
    base = (
        select(Transaction)
        .where(
            Transaction.property_type == listing.property_type,
            Transaction.rooms.between(listing.rooms - 1, listing.rooms + 1),
            Transaction.sqm.between(listing.sqm * 0.8, listing.sqm * 1.2),
            Transaction.deal_date >= date.today() - timedelta(days=18*30),
        )
    )
    # Step 2: widening radius
    for radius_m, min_count, conf in [(500, 10, "high"), (1000, 5, "medium"), (2000, 3, "low")]:
        q = base.where(
            func.ST_DWithin(
                Transaction.geom.cast(Geography),
                listing.geom.cast(Geography),
                radius_m
            )
        )
        rows = db.execute(q).scalars().all()
        if len(rows) >= min_count:
            ppsqms = sorted(float(r.price) / float(r.sqm) for r in rows)
            # 5% trim each side
            trim = max(1, int(len(ppsqms) * 0.05))
            trimmed = ppsqms[trim:-trim] if len(ppsqms) > 2*trim else ppsqms
            median = statistics.median(trimmed)
            estimated = median * float(listing.sqm)
            discount = (estimated - float(listing.price)) / estimated
            return Valuation(
                estimated_value=estimated,
                median_ppsqm=median,
                comparable_count=len(rows),
                radius_m=radius_m,
                confidence=conf,
                discount_percent=discount,
            )
    return None  # insufficient
```

---

## 8. Listing adapter contract

```python
class ListingAdapter(ABC):
    @abstractmethod
    async def search(
        self,
        city: str,
        rooms_min: int,
        rooms_max: int,
        price_max: int,
        max_pages: int,
        property_type: str,
    ) -> list[RawListing]: ...
```

`RawListing` = dataclass with `source`, `source_listing_id`, `city`, `address`, `rooms`, `sqm`,
`price`, `property_type`, `url`, `lat`, `lon`, `raw_json`.

Two implementations ship:
- `SampleAdapter` — reads `backend/data/sample_listings.json` and applies the filters in Python.
- `Yad2Adapter` — Playwright-based; respects 1 req / 3 s; gated on `LISTING_SOURCE=yad2`; ships
  with a `pytest.mark.skip` integration test.

Selection lives in `app/adapters/__init__.py` via `get_adapter(name)` and is read once at
startup from `settings.listing_source` (default `sample`).

---

## 9. Geocoding (MVP)

There is no real geocoder. The sample data ships pre-geocoded. For scraped listings without
coordinates we use a **city-centroid + small random offset** approach:

- `geo.CITY_CENTROIDS = { "Tel Aviv": (32.0853, 34.7818), ... }`
- A listing without coordinates is placed at `centroid + N(0, 0.005°)` (~500 m std).
- This is good enough for MVP because comparables are picked at 500 m – 2 km radius.

This trade-off is documented in the README under "Limitations".

---

## 10. Configuration

`.env.example`:
```
POSTGRES_USER=nadlan
POSTGRES_PASSWORD=nadlan
POSTGRES_DB=nadlan
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

BACKEND_PORT=8000
FRONTEND_PORT=3000

LISTING_SOURCE=sample      # sample | yad2
SCRAPE_RATE_LIMIT_S=3
AUTO_SEED=true             # if true, seed sample CSV on startup when transactions table is empty

NEXT_PUBLIC_API_URL=http://localhost:8000
```

`config.py` uses `pydantic-settings.BaseSettings`.

---

## 11. Docker

### `docker-compose.yml`
```yaml
services:
  postgres:
    image: postgis/postgis:16-3.4
    env_file: .env
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 10
    ports:
      - "5432:5432"  # convenient for local psql; can be removed

  backend:
    build: ./backend
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${BACKEND_PORT}:8000"
    volumes:
      - ./backend/data:/data:ro

  frontend:
    build: ./frontend
    env_file: .env
    depends_on:
      - backend
    ports:
      - "${FRONTEND_PORT}:3000"

volumes:
  pgdata:
```

### `backend/Dockerfile`
- Base: `python:3.12-slim`.
- Install: `gdal-bin libgeos-dev` (for shapely), then `pip install -r requirements.txt`.
- Skip Playwright Chromium install in the default build to keep image small (the sample adapter
  is the default). Provide a `Dockerfile.playwright` for users who want Yad2.
- `CMD ["bash", "-lc", "alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]`

### `frontend/Dockerfile`
- Base: `node:20-alpine`.
- `npm ci && npm run build && CMD ["npm", "start"]`.

---

## 12. Non-functional implementation notes

| NFR | Implementation |
|-----|---------------|
| NFR-1 (≤60s scan) | Sample adapter returns in ms. Valuation queries are indexed (GIST + composite). |
| NFR-2 (≤90s boot) | Slim images; no Playwright Chromium by default. |
| NFR-3 (persistence) | Named volume `pgdata`. |
| NFR-4 (no secrets in source) | `.env.example` only; `.env` is gitignored. |
| NFR-5 (≥70% coverage) | `pytest --cov=app/services --cov=app/adapters --cov-fail-under=70` in CI snippet (CI itself is out of MVP scope but Makefile target is provided). |
| NFR-6 (frontend lint) | `next lint` runs in Dockerfile build step. |
| NFR-7 (structured logs) | `structlog.processors.JSONRenderer`. |
| NFR-8 (rate limit) | `asyncio.Semaphore(1)` + adapter-internal `await asyncio.sleep(3)`. |
| NFR-9 (input validation) | Pydantic enforces; `city` validated against allow-list from DB. |

---

## 13. Failure modes & handling

| Failure | Handling |
|---------|----------|
| Postgres down at startup | Backend retries connection 30× w/ 2s backoff before exit. |
| Adapter raises | scan_runs.status = "error", error_msg = exception class + message. |
| Listing missing geom | Falls back to city centroid + offset (logged warning). |
| Empty transactions table | `/scan` succeeds but all listings end up "skipped: insufficient". Frontend has dedicated empty-DB copy. |
| Concurrent /scan calls | Semaphore queues them; client sees `status=queued` until prior finishes. |

---

## 14. Deployment

Strictly local for MVP:

```
git clone https://github.com/dalali/nadlan-genie
cd nadlan-genie
cp .env.example .env
docker compose up --build
```

Open `http://localhost:3000`. First boot auto-seeds the bundled sample transactions because
`AUTO_SEED=true`.

No CI/CD, no cloud, no Kubernetes. A `Makefile` provides convenience targets:
```
make up        # docker compose up --build
make down
make logs
make test      # runs backend pytest in a temp container
make psql      # opens psql shell into postgres container
```

---

## 15. Open items deferred to v2

- Hebrew RTL UI.
- Map view (Leaflet + tile cache).
- Real geocoder (Nominatim self-hosted container).
- Multi-source scans (Yad2 + Madlan in parallel).
- Saved searches + email alerts (would require background worker; out of MVP).
- Neighbourhood-tier price adjustment.
