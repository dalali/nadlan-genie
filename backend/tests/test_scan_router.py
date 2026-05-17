"""Validation tests for the /scan endpoint.

The endpoint requires a DB session; we provide a no-op stub and a fake `run_scan` so
nothing actually runs. The goal is to verify request validation and the 202 contract.
"""
from __future__ import annotations

import asyncio
import datetime as dt
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class _FakeScanRun:
    def __init__(self, **kwargs) -> None:
        self.id = kwargs.get("id") or uuid.uuid4()
        for k, v in kwargs.items():
            setattr(self, k, v)


class _FakeSession:
    """Session stub with a configurable ``get`` for ScanRun lookups."""

    def __init__(self, scan_by_id: dict | None = None) -> None:
        self._scan_by_id = scan_by_id or {}
        self.committed = False

    def add(self, _obj) -> None:
        pass

    def commit(self) -> None:
        self.committed = True

    def refresh(self, _obj) -> None:
        pass

    def get(self, _model, key):  # noqa: ANN001
        return self._scan_by_id.get(key)

    def query(self, *_models):  # noqa: ANN001
        class _Q:
            def join(self_inner, *a, **kw):
                return self_inner

            def filter(self_inner, *a, **kw):
                return self_inner

            def order_by(self_inner, *a, **kw):
                return self_inner

            def all(self_inner):
                return []

        return _Q()

    def execute(self, _stmt):  # noqa: ANN001
        # Used by the city allow-list check; an empty DB falls back to SUPPORTED_CITIES.
        class _Result:
            def all(self_inner):
                return []
        return _Result()


@pytest.fixture()
def client(monkeypatch):
    from app.routers import scan as scan_router

    async def _fake_run_scan(scan_id, filters):  # noqa: ANN001
        # Sleep briefly so the task doesn't immediately exit (still under test runtime).
        await asyncio.sleep(0)

    monkeypatch.setattr(scan_router, "run_scan", _fake_run_scan)

    from app.deps import get_db

    def _fake_db():
        yield _FakeSession()

    app = FastAPI()
    app.include_router(scan_router.router)
    app.dependency_overrides[get_db] = _fake_db
    return TestClient(app)


def test_scan_happy_path_returns_202_with_uuid(client: TestClient):
    r = client.post(
        "/scan",
        json={
            "city": "Ramat Gan",
            "rooms_min": 3,
            "rooms_max": 4,
            "price_max": 3_000_000,
            "discount_threshold": 0.15,
            "max_pages": 3,
            "property_type": "apartment",
        },
    )
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    # UUID parses cleanly.
    uuid.UUID(body["scan_id"])


def test_scan_rejects_rooms_inverted(client: TestClient):
    r = client.post(
        "/scan",
        json={
            "city": "Ramat Gan",
            "rooms_min": 5,
            "rooms_max": 2,
            "price_max": 3_000_000,
            "discount_threshold": 0.15,
            "max_pages": 3,
            "property_type": "apartment",
        },
    )
    assert r.status_code == 422


def test_scan_rejects_excess_pages(client: TestClient):
    r = client.post(
        "/scan",
        json={
            "city": "Ramat Gan",
            "rooms_min": 3,
            "rooms_max": 4,
            "price_max": 3_000_000,
            "discount_threshold": 0.15,
            "max_pages": 99,
            "property_type": "apartment",
        },
    )
    assert r.status_code == 422


def test_scan_rejects_extra_keys(client: TestClient):
    # ScanRequest has extra="forbid".
    r = client.post(
        "/scan",
        json={
            "city": "Ramat Gan",
            "rooms_min": 3,
            "rooms_max": 4,
            "price_max": 3_000_000,
            "discount_threshold": 0.15,
            "max_pages": 3,
            "property_type": "apartment",
            "lat": 32.0,
        },
    )
    assert r.status_code == 422


def test_scan_rejects_unknown_property_type(client: TestClient):
    r = client.post(
        "/scan",
        json={
            "city": "Ramat Gan",
            "rooms_min": 3,
            "rooms_max": 4,
            "price_max": 3_000_000,
            "discount_threshold": 0.15,
            "max_pages": 3,
            "property_type": "land",
        },
    )
    assert r.status_code == 422


def test_scan_rejects_zero_price_max(client: TestClient):
    r = client.post(
        "/scan",
        json={
            "city": "Ramat Gan",
            "rooms_min": 3,
            "rooms_max": 4,
            "price_max": 0,
            "discount_threshold": 0.15,
            "max_pages": 3,
            "property_type": "apartment",
        },
    )
    assert r.status_code == 422


# ---------------------------------------------------------------------------
# GET /scan/{scan_id} and DELETE /scan/{scan_id}  (QA LOW-8)
# ---------------------------------------------------------------------------


def _make_client(session: _FakeSession) -> TestClient:
    """Wire the scan router up with a single session instance so we can
    inspect mutations across one request."""
    from app.deps import get_db
    from app.routers import scan as scan_router

    app = FastAPI()
    app.include_router(scan_router.router)

    def _override():
        yield session

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def test_get_scan_returns_404_when_missing():
    session = _FakeSession(scan_by_id={})
    client = _make_client(session)
    r = client.get(f"/scan/{uuid.uuid4()}")
    assert r.status_code == 404
    assert r.json()["detail"] == "scan not found"


def test_get_scan_returns_queued_run_with_empty_results():
    scan_id = uuid.uuid4()
    scan = _FakeScanRun(
        id=scan_id,
        status="queued",
        step="scrape",
        filters_json={"city": "Ramat Gan"},
        requested_at=dt.datetime(2026, 1, 1, 10, 0, 0),
        finished_at=None,
        result_count=None,
        error_msg=None,
        skipped_json=None,
    )
    client = _make_client(_FakeSession(scan_by_id={scan_id: scan}))
    r = client.get(f"/scan/{scan_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["scan_id"] == str(scan_id)
    # Results are only populated on a done scan.
    assert body["results"] == []
    assert body["skipped"] == []


def test_get_scan_returns_done_with_no_rows():
    """Even when status='done', a session with no joined rows returns []."""
    scan_id = uuid.uuid4()
    scan = _FakeScanRun(
        id=scan_id,
        status="done",
        step="rank",
        filters_json={"city": "Ramat Gan"},
        requested_at=dt.datetime(2026, 1, 1, 10, 0, 0),
        finished_at=dt.datetime(2026, 1, 1, 10, 0, 30),
        result_count=0,
        error_msg=None,
        skipped_json=[{"url": "https://example.com/x", "reason": "no comparables"}],
    )
    client = _make_client(_FakeSession(scan_by_id={scan_id: scan}))
    r = client.get(f"/scan/{scan_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "done"
    assert body["results"] == []  # fake query returns []
    assert body["skipped"] == [{"url": "https://example.com/x", "reason": "no comparables"}]


def test_delete_scan_returns_404_when_missing():
    client = _make_client(_FakeSession(scan_by_id={}))
    r = client.delete(f"/scan/{uuid.uuid4()}")
    assert r.status_code == 404


def test_delete_scan_returns_terminal_status_for_done_run():
    scan_id = uuid.uuid4()
    scan = _FakeScanRun(
        id=scan_id,
        status="done",
        error_msg=None,
    )
    session = _FakeSession(scan_by_id={scan_id: scan})
    client = _make_client(session)
    r = client.delete(f"/scan/{scan_id}")
    assert r.status_code == 200
    assert r.json() == {"status": "done"}
    # We must not commit a status change for an already-terminal run.
    assert session.committed is False
    assert scan.status == "done"


def test_delete_scan_marks_running_scan_cancelled():
    scan_id = uuid.uuid4()
    scan = _FakeScanRun(
        id=scan_id,
        status="running",
        error_msg=None,
    )
    session = _FakeSession(scan_by_id={scan_id: scan})
    client = _make_client(session)
    r = client.delete(f"/scan/{scan_id}")
    assert r.status_code == 200
    assert r.json() == {"status": "cancelled"}
    # Side effects: status flipped to error, error_msg set, commit called.
    assert scan.status == "error"
    assert scan.error_msg == "cancelled"
    assert session.committed is True
