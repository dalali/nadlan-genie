"""Tests for the CSV importer's column validation and streaming behaviour.

The full insert path requires PostGIS; we test the parts that don't.
"""
from __future__ import annotations

import io

import pytest

from app.services.importer import REQUIRED_COLUMNS, import_csv


class _FakeRow:
    """Row-like object exposing both attribute access and ._mapping."""

    def __init__(self, id_: int, xmax_text: str = "0") -> None:
        self.id = id_
        self.xmax_text = xmax_text
        self._mapping = {"id": id_, "xmax_text": xmax_text}


class _FakeSession:
    """Tiny stub that records insert statements without touching a real DB.

    By default every execute() reports xmax_text='0' (i.e. row newly inserted).
    Tests can override this by setting ``xmax_text`` on the instance before
    calling import_csv.
    """

    def __init__(self, xmax_text: str = "0") -> None:
        self.executed: list[object] = []
        self.committed = False
        self.xmax_text = xmax_text

    def execute(self, stmt):  # noqa: ANN001
        self.executed.append(stmt)

        outer = self

        class _Result:
            def first(self_inner):
                return _FakeRow(1, outer.xmax_text)

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


def test_import_csv_counts_inserts_vs_updates_via_xmax():
    """Rows whose ON CONFLICT triggered an UPDATE report xmax != '0'."""
    csv_text = (
        "deal_id,deal_date,city,property_type,rooms,sqm,price,lat,lon\n"
        "1,2025-01-01,Tel Aviv,apartment,3,70,2500000,32.08,34.78\n"
        "2,2025-01-02,Tel Aviv,apartment,3,70,2600000,32.08,34.78\n"
    )

    # Default fake: every row appears as newly inserted (xmax_text='0').
    fake_insert = _FakeSession(xmax_text="0")
    stats_ins = import_csv(io.StringIO(csv_text), fake_insert)  # type: ignore[arg-type]
    assert stats_ins["inserted"] == 2
    assert stats_ins["updated"] == 0

    # Same CSV but the fake reports xmax != '0' (i.e. existing row updated).
    fake_update = _FakeSession(xmax_text="12345")
    stats_upd = import_csv(io.StringIO(csv_text), fake_update)  # type: ignore[arg-type]
    assert stats_upd["inserted"] == 0
    assert stats_upd["updated"] == 2
