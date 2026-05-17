"""Validation tests for the /scan endpoint.

The endpoint requires a DB session; we provide a no-op stub and a fake `run_scan` so
nothing actually runs. The goal is to verify request validation and the 202 contract.
"""
from __future__ import annotations

import asyncio
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
    def add(self, _obj) -> None:
        pass

    def commit(self) -> None:
        pass

    def refresh(self, _obj) -> None:
        pass

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
