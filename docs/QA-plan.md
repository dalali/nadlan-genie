# nadlan-genie — QA Plan

**Iteration:** 1
**Last updated:** 2026-05-17

## 1. Test surface

The MVP has three independent execution contexts:

| Context | Reach | How it's tested |
|---------|-------|-----------------|
| Pure Python logic | valuation math, geo helpers, schema validation, importer parsing, adapter filtering, router validation | `pytest` — runs in any environment with Python + deps installed. No DB. |
| Backend + Postgres + PostGIS | full `/scan` lifecycle, `/health`, `/cities`, `/import-transactions` end-to-end | `make test` (spins up the compose stack and runs the integration suite). Marked `pytest.mark.integration` and auto-skipped when DB unreachable. |
| Frontend (browser) | dashboard interactions, form submission, polling, history navigation | Manual smoke test against `docker compose up`. No automated browser tests in MVP (deferred). |

## 2. What passes without Docker

Run from `backend/`:

```bash
pytest -v --ignore=tests/test_health_integration.py
```

Covers (56 tests as of iteration 1):

- `test_valuation_pure.py` — trimmed median correctness, outlier rejection.
- `test_valuation_logic.py` — discount arithmetic, linearity, edge cases.
- `test_geo.py` — supported-city list, jitter determinism, Israel bounding-box.
- `test_schemas.py` — Pydantic validation for `ScanRequest` (rooms, pages, type, price).
- `test_adapters.py` — `SampleAdapter` filters, factory dispatch, Yad2 stub.
- `test_importer_parse.py` — single-row date / numeric parsing.
- `test_importer_csv.py` — missing columns, skipped rows, empty file, required-column drift.
- `test_scan_router.py` — `/scan` happy-path + 5 422 cases (no DB; DB dep is overridden).
- `test_transactions_router.py` — multipart streaming + JSON dispatch + Content-Type errors (no DB).

## 3. What requires Docker

`tests/test_health_integration.py` — needs `postgres:5432` reachable with PostGIS extension. Skipped when not.

Acceptance scans (per PRD §14):

| Scan | Expected |
|------|----------|
| Ramat Gan, 3-4 rooms, ≤ ₪3M, threshold 0.0 | ≥ 1 result, status=done |
| Tel Aviv, 2-5 rooms, ≤ ₪6M, threshold 0.15 | 5-20 results within 10 s |
| Jerusalem, 4-5 rooms, ≤ ₪4M, threshold 0.10 | results sorted by discount % desc |
| Haifa, 1-3 rooms, ≤ ₪2M, threshold 0.20 | confidence labels present |
| Tel Aviv (empty DB simulation) | all listings appear in `skipped` with reason=`insufficient_comparables` |

## 4. User-story coverage

| Story | Coverage |
|-------|----------|
| US-1 first-run | `docker compose up --build` + auto-seed via `maybe_auto_seed()`. Verified by `make up` smoke test. |
| US-2 on-demand scan | `test_scan_router.py` covers the API contract; `test_health_integration.py::test_scan_lifecycle` covers the end-to-end async lifecycle. |
| US-3 ranked results | `test_valuation_logic.py` proves discount math; `scan_runner.py` sorts by `discount_percent` desc; manual frontend smoke test confirms colour coding. |
| US-4 re-import / refresh | `test_importer_csv.py` + `test_transactions_router.py` cover both modes. Streaming verified by `_stream_to_tempfile` writing in 64 KB chunks. |
| US-5 history | `GET /results` covered by `test_results.py` (added in this iteration via the integration test setup) + frontend HistoryPanel manual check. |
| US-6 health | `test_health_integration.py::test_health_ok`. |

## 5. Coverage gaps (accepted for MVP)

- No headless-browser tests for the Next.js frontend. The components are visually trivial and verified by smoke test; e2e is a v2 item.
- `value_listing` is not unit-tested with a real PostGIS query — exercised only via the integration `/scan` test. Splitting the geographic filter into a mockable layer is a v2 refactor.
- `Yad2Adapter` is not covered beyond the "raises NotImplementedError" guard, by design.

## 6. How to run

```bash
# pure tests
cd backend && pytest -v --ignore=tests/test_health_integration.py

# full stack including integration
make up-d            # bring up postgres + backend
make test            # runs pytest -q in a temp container; uses the live DB
```
