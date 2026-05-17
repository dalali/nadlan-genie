"""Tests for the /import-transactions Content-Type dispatcher.

These tests do not need a live database — they exercise only the request validation /
dispatch logic by monkey-patching the importer functions.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch):
    # Stub the importer so we don't need PostGIS.
    from app.routers import transactions as tx_router

    def _fake_import_csv(fileobj, db, **_):  # noqa: ANN001
        # Consume the stream so we exercise the spool-to-tempfile path.
        content = fileobj.read() if hasattr(fileobj, "read") else ""
        return {"inserted": content.count("\n"), "updated": 0, "skipped": 0, "total": content.count("\n")}

    def _fake_import_path(path, db):  # noqa: ANN001
        if path == "/nope":
            raise FileNotFoundError(path)
        return {"inserted": 7, "updated": 0, "skipped": 0, "total": 7}

    monkeypatch.setattr(tx_router, "import_csv", _fake_import_csv)
    monkeypatch.setattr(tx_router, "import_path", _fake_import_path)

    # Override the DB dependency so we never touch SQLAlchemy at all.
    from app.deps import get_db

    def _no_db():
        yield None

    app = FastAPI()
    app.include_router(tx_router.router)
    app.dependency_overrides[get_db] = _no_db
    return TestClient(app)


def test_import_multipart_streams_and_counts(client: TestClient):
    csv = (
        "deal_id,deal_date,city,property_type,rooms,sqm,price,lat,lon\n"
        "1,2025-01-01,Tel Aviv,apartment,3,70,2500000,32.08,34.78\n"
        "2,2025-01-02,Tel Aviv,apartment,3,70,2600000,32.08,34.78\n"
    )
    r = client.post(
        "/import-transactions",
        files={"file": ("sample.csv", csv, "text/csv")},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3  # 3 newlines counted by the stub
    assert body["inserted"] == 3


def test_import_json_by_path_ok(client: TestClient):
    r = client.post(
        "/import-transactions",
        json={"path": "/app/data/sample_transactions.csv"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["inserted"] == 7


def test_import_json_path_missing_returns_404(client: TestClient):
    r = client.post("/import-transactions", json={"path": "/nope"})
    assert r.status_code == 404


def test_import_no_body_returns_400(client: TestClient):
    r = client.post("/import-transactions")
    assert r.status_code == 400
    assert "multipart" in r.json()["detail"].lower()


def test_import_json_extra_keys_rejected(client: TestClient):
    # ImportByPath has extra="forbid" — random keys should 422 (validation error).
    r = client.post(
        "/import-transactions",
        json={"path": "/tmp/x", "nukes": True},
    )
    assert r.status_code == 422
