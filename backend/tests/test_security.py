"""Security regression tests for input validation and path-traversal guards.

Layered on top of test_scan_router.py and test_transactions_router.py — these tests
specifically guard the fixes made in the security-review phase of iteration 1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.importer import _is_under_allowed_root


# --- import_path traversal guard ---------------------------------------------------------

@pytest.mark.parametrize(
    "p",
    [
        "/data/foo.csv",
        "/data/sub/bar.csv",
        "/app/data/sample_transactions.csv",
        "/data",  # the root itself
    ],
)
def test_allowed_root_accepts_data_paths(p: str):
    assert _is_under_allowed_root(Path(p)) is True


@pytest.mark.parametrize(
    "p",
    [
        "/etc/passwd",
        "/etc/shadow",
        "/proc/1/environ",
        "/root/secrets",
        "/tmp/anything.csv",
        "/data/../etc/passwd",  # resolves outside /data
        "../../etc/passwd",
    ],
)
def test_allowed_root_rejects_traversal(p: str):
    assert _is_under_allowed_root(Path(p)) is False


# --- scan city allow-list ---------------------------------------------------------------

def test_scan_rejects_unknown_city(monkeypatch):
    """The /scan endpoint must 422 when city is outside the allow-list (NFR-9)."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.deps import get_db
    from app.routers import scan as scan_router

    async def _no_run(scan_id, filters):  # noqa: ANN001
        return None

    class _FakeSession:
        def add(self, _o): pass
        def commit(self): pass
        def refresh(self, _o): pass
        def execute(self, _stmt):
            class _R:
                def all(self_inner): return []
            return _R()

    monkeypatch.setattr(scan_router, "run_scan", _no_run)
    app = FastAPI()
    app.include_router(scan_router.router)
    def _fake_db():
        yield _FakeSession()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    r = client.post(
        "/scan",
        json={
            "city": "Atlantis",  # not in SUPPORTED_CITIES, not in (empty) DB
            "rooms_min": 3,
            "rooms_max": 4,
            "price_max": 3_000_000,
            "discount_threshold": 0.15,
            "max_pages": 3,
            "property_type": "apartment",
        },
    )
    assert r.status_code == 422
    assert "supported" in r.text.lower()


def test_scan_accepts_supported_city(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.deps import get_db
    from app.routers import scan as scan_router

    async def _no_run(scan_id, filters):  # noqa: ANN001
        return None

    class _FakeSession:
        def add(self, _o): pass
        def commit(self): pass
        def refresh(self, _o): pass
        def execute(self, _stmt):
            class _R:
                def all(self_inner): return []
            return _R()

    monkeypatch.setattr(scan_router, "run_scan", _no_run)
    app = FastAPI()
    app.include_router(scan_router.router)
    def _fake_db():
        yield _FakeSession()

    app.dependency_overrides[get_db] = _fake_db
    client = TestClient(app)

    r = client.post(
        "/scan",
        json={
            "city": "Tel Aviv",
            "rooms_min": 3,
            "rooms_max": 4,
            "price_max": 3_000_000,
            "discount_threshold": 0.15,
            "max_pages": 3,
            "property_type": "apartment",
        },
    )
    assert r.status_code == 202, r.text
