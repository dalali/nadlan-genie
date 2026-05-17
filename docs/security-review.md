# nadlan-genie — Security Review

**Iteration:** 1
**Last updated:** 2026-05-17
**Reviewer:** project-manager (security-analyst role)
**Verdict:** PASS (after iteration-1 fixes)

The app is local-first and single-user, which narrows the threat model substantially. The main
realistic threats are (a) a malicious CSV import abusing the file-path mode of the importer, and
(b) a hostile webpage in another browser tab trying to drive the local backend via CSRF-style
cross-origin requests. Both are addressed below.

## 1. Threat model (one paragraph)

A single trusted user runs the stack on their own laptop. There is no auth, no multi-tenant
data, no network exposure beyond `localhost:3000` and `localhost:8000`. The only third party
ever reachable by the backend is the user's chosen listing source (default: a bundled JSON
fixture, so zero network egress). The data of value is: nothing — there is no PII, no secrets,
no transactional money flow. Therefore the security bar is: don't actively make the laptop less
safe than it was.

## 2. Findings & resolutions

| ID | Severity | Area | Finding | Resolution |
|----|----------|------|---------|------------|
| S-1 | Medium | API edge / NFR-9 | `/scan` accepted any string for `city`, violating the documented allow-list requirement. Could trigger unindexed full-table scans and skew telemetry. | Added `_allowed_cities()` check that validates against the union of DB cities and the hard-coded `SUPPORTED_CITIES` list. 422 with the allowed set on mismatch. |
| S-2 | Medium | File handling | `POST /import-transactions` with JSON `{path: ...}` mode opened **any** path the backend process could read (`/etc/passwd`, `/proc/<pid>/environ`, container filesystem in general). It would fail with `ValueError` on CSV parse, but the file-read primitive is still real. | Added `_is_under_allowed_root()` that constrains the path to `/data` or `/app/data` (the read-only bind mount of `backend/data/`). Tests cover 7 traversal vectors. |
| S-3 | Low | Browser cross-origin | CORS was `allow_origins=["*"]` with all methods. A hostile webpage open in another tab could `fetch` against `localhost:8000` and trigger scans, fill the DB, etc. | Restricted to `http://localhost:3000` and `http://127.0.0.1:3000`, `allow_credentials=False`, explicit method allow-list. |
| S-4 | Informational | Docker | `docker-compose.yml` exposes Postgres on `0.0.0.0:5432` with default creds `nadlan/nadlan`. Anyone on the same Wi-Fi can connect. | Documented; not fixed in iteration 1 because the convenience of `make psql` from the host is valuable for the MVP demo audience. Mitigation: change the `.env` password before running on an untrusted network, or bind to `127.0.0.1:5432:5432` in compose. |
| S-5 | Informational | DoS | Importer has no row-count cap; uploading a 10 GB CSV would loop indefinitely. | Out of scope: local-only single user can DoS themselves but nothing else. Streamed-to-tempfile + 64 KB chunks keeps RAM bounded. |
| S-6 | Informational | Frontend | `ResultTable` renders `listing.url` directly into `<a href>`. React escapes attribute content, so XSS via the href is mitigated, but a `javascript:` URL would still execute on click. Sample data is trusted; not a real risk today. | Not fixed in iteration 1. v2 add: `url.startsWith('http')` guard before rendering as a link. |
| S-7 | Pass | SQL injection | All queries use SQLAlchemy ORM with parameterised binds. The one WKT string is interpolated from `float()`-parsed lat/lon, so injection is not possible. | — |
| S-8 | Pass | Secrets in source | `.env` is gitignored, `.env.example` ships placeholder credentials only. `git log` reviewed — no leaks. | — |
| S-9 | Pass | Dependencies | All pinned. Versions checked against PyPI / NPM advisory feeds as of 2026-05-17 — no known CVEs in `fastapi==0.115.0`, `SQLAlchemy==2.0.35`, `psycopg==3.2.3`, `pydantic==2.9.2`, `next@14.2.13`, `python-multipart==0.0.12`. | — |

## 3. Tests covering the fixes

`backend/tests/test_security.py` (13 tests):
- 4 accept-cases for `_is_under_allowed_root` on `/data` paths.
- 7 reject-cases for `_is_under_allowed_root` (incl. `..` traversal, `/etc/passwd`, `/proc/...`).
- 1 test that `/scan` returns 422 for an unknown city with a helpful detail.
- 1 test that `/scan` returns 202 for a supported city.

Full backend suite (69 tests) passes in 0.33 s.

## 4. Residual risk acknowledgement

For an MVP deployed only via `docker compose up` on a developer laptop, the post-fix posture is
acceptable. If the project ever exposes the backend on a public interface, S-4/S-5/S-6 graduate
to blocking issues and an authentication layer becomes mandatory.
