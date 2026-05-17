"""Tests for the CSV importer's column validation and streaming behaviour.

The full insert path requires PostGIS; we test the parts that don't.
"""
from __future__ import annotations

import io

import pytest

from app.services.importer import REQUIRED_COLUMNS, import_csv


class _FakeSession:
    """Tiny stub that records insert statements without touching a real DB."""

    def __init__(self) -> None:
        self.executed: list[object] = []
        self.committed = False

    def execute(self, stmt):  # noqa: ANN001
        self.executed.append(stmt)

        class _Result:
            def first(self_inner):
                return (1,)

            def scalar_one(self_inner):
                return 1

        return _Result()

    def commit(self) -> None:
        self.committed = True


def test_import_csv_rejects_missing_columns():
    csv_text = "deal_id,deal_date,city\n1,2025-01-01,Tel Aviv\n"
    with pytest.raises(ValueError) as excinfo:
        import_csv(io.StringIO(csv_text), _FakeSession())  # type: ignore[arg-type]
    msg = str(excinfo.value)
    for missing in ("price", "lat", "lon", "property_type"):
        assert missing in msg, f"error must mention missing column {missing!r}"


def test_required_columns_match_documented_schema():
    # If someone adds/removes a required column, the seed CSV header must change too.
    assert REQUIRED_COLUMNS == {
        "deal_id",
        "deal_date",
        "city",
        "property_type",
        "rooms",
        "sqm",
        "price",
        "lat",
        "lon",
    }


def test_import_csv_counts_skipped_rows():
    csv_text = (
        "deal_id,deal_date,city,property_type,rooms,sqm,price,lat,lon\n"
        "1,2025-01-01,Tel Aviv,apartment,3,70,2500000,32.08,34.78\n"
        "2,not-a-date,Tel Aviv,apartment,3,70,2500000,32.08,34.78\n"
        "3,2025-01-01,Tel Aviv,apartment,3,70,0,32.08,34.78\n"
    )
    fake = _FakeSession()
    stats = import_csv(io.StringIO(csv_text), fake)  # type: ignore[arg-type]
    assert stats["total"] == 3
    assert stats["skipped"] == 2  # bad date + zero price
    assert fake.committed is True


def test_import_csv_empty_file_is_valid():
    csv_text = "deal_id,deal_date,city,property_type,rooms,sqm,price,lat,lon\n"
    stats = import_csv(io.StringIO(csv_text), _FakeSession())  # type: ignore[arg-type]
    assert stats == {"inserted": 0, "updated": 0, "skipped": 0, "total": 0}
