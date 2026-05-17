"""Integration tests that hit the real Postgres in the docker-compose stack.

Run via `make test` (which spins up postgres). Skipped when DB unreachable.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

pytestmark = pytest.mark.integration


def _db_reachable() -> bool:
    try:
        from app.db import engine

        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.fixture(scope="module")
def client():
    if not _db_reachable():
        pytest.skip("Postgres unreachable; skip integration suite")
    from app.main import app

    return TestClient(app)


def test_health_ok(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["postgres"] == "ok"
    assert body["transactions_loaded"] >= 0


def test_cities_returns_supported_or_db(client: TestClient):
    r = client.get("/cities")
    assert r.status_code == 200
    assert "cities" in r.json()
    assert isinstance(r.json()["cities"], list)


def test_scan_lifecycle(client: TestClient):
    # Seed via the bundled CSV path if table is empty
    health = client.get("/health").json()
    if health["transactions_loaded"] == 0:
        r = client.post(
            "/import-transactions",
            json={"path": "/app/data/sample_transactions.csv"},
        )
        assert r.status_code == 200, r.text

    r = client.post(
        "/scan",
        json={
            "city": "Ramat Gan",
            "rooms_min": 3,
            "rooms_max": 4,
            "price_max": 5_000_000,
            "discount_threshold": 0.0,
            "max_pages": 3,
            "property_type": "apartment",
        },
    )
    assert r.status_code == 202, r.text
    scan_id = r.json()["scan_id"]

    # Poll up to 30s
    import time

    for _ in range(60):
        time.sleep(0.5)
        d = client.get(f"/scan/{scan_id}").json()
        if d["status"] in ("done", "error"):
            break
    assert d["status"] == "done", d
    assert isinstance(d["results"], list)
