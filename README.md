# nadlan-genie

Local-first MVP that finds **potentially underpriced residential properties for sale in Israel**
by comparing live listings against locally stored Israeli transaction (sales) data.

- Runs **entirely on your laptop** via `docker compose up --build`.
- **No LLMs, no paid APIs, no cloud**, no background crawlers.
- Single-city, on-demand scans. Target runtime: 10–60 seconds.
- Deterministic valuation from comparable sales (median ₪/sqm in a widening radius).

## Quick start

```bash
git clone https://github.com/dalali/nadlan-genie
cd nadlan-genie
make up        # auto-copies .env.example -> .env if missing, then docker compose up --build
```

If you prefer to invoke docker compose directly, copy the env file first:

```bash
cp .env.example .env
docker compose up --build
```

Then open <http://localhost:3000>.

On first boot the backend automatically imports the bundled sample transaction CSV (~5,000
deals across Tel Aviv, Ramat Gan, Haifa, and Jerusalem) and the sample listings adapter so the
app is functional out-of-the-box.

## How a scan works

1. You pick a city and filters (rooms range, max price, discount threshold, max pages).
2. Click **Scan Now**. Backend scrapes a small number of current listings (max 3 pages, ~50 items).
3. For each listing, the valuation engine finds comparable sold properties (similar rooms, sqm,
   property type) within a widening geographic radius (500 m → 1 km → 2 km).
4. It computes the median ₪/sqm of those comparables, multiplies by the listing's sqm to get an
   **estimated market value**, and reports the discount %.
5. Results are ranked by discount %, filtered by your threshold, and shown with a confidence score
   (High / Medium / Low based on comparable count and radius).

## Limitations (MVP)

- **Default listing source is the bundled sample adapter.** Real adapters (e.g. Yad2) can be enabled
  by setting `LISTING_SOURCE=yad2` in `.env`, but they are disabled by default because the listing
  sources block automated traffic and the project policy forbids anti-bot bypass.
- Geocoding is approximate: scraped listings without coordinates are placed at the **city centroid
  with a small random offset**. Comparable selection uses 500 m – 2 km radii, so this is good
  enough for ranking but should not be relied on for precise location.
- Transaction data is a **sample**. For production use, download a current export from the Israel
  Ministry of Finance open-data portal and import via `POST /import-transactions`.
- Single-user, single-process. No auth, no multi-tenant.
- English UI. Hebrew RTL is deferred to v2.

## Architecture

See [`docs/architecture.md`](docs/architecture.md). TL;DR: Next.js 14 frontend, FastAPI backend,
Postgres + PostGIS, all behind a single `docker compose` stack.

## Documents

- [`docs/PRD.md`](docs/PRD.md) — product requirements
- [`docs/design.md`](docs/design.md) — UI/UX
- [`docs/architecture.md`](docs/architecture.md) — architecture & data model

## Project layout

```
backend/    FastAPI + SQLAlchemy + PostGIS
frontend/   Next.js 14 + Tailwind + TypeScript
docs/       PRD, design, architecture
```

## Make targets

| Target | What it does |
|--------|--------------|
| `make env` | Copy `.env.example` to `.env` if missing |
| `make up` (alias: `make dev`) | Ensure `.env` exists, then `docker compose up --build` |
| `make up-d` | Same, detached |
| `make down` | Stop and remove containers (keep volume) |
| `make clean` | `docker compose down -v` (also removes the postgres volume) |
| `make logs` | Follow combined logs |
| `make test` | Run backend pytest suite in a one-off container |
| `make psql` | Open psql in the postgres container |

## License

MIT (placeholder).
