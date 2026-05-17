from __future__ import annotations

from app.services.importer import _parse_date, _parse_row


def test_parse_date_iso():
    d = _parse_date("2026-05-17")
    assert d.year == 2026 and d.month == 5 and d.day == 17


def test_parse_date_dmy():
    d = _parse_date("17/05/2026")
    assert d.year == 2026 and d.month == 5 and d.day == 17


def test_parse_row_happy_path():
    row = {
        "deal_id": "100",
        "deal_date": "2026-01-01",
        "city": "Tel Aviv",
        "property_type": "apartment",
        "rooms": "3",
        "sqm": "70",
        "price": "2500000",
        "lat": "32.08",
        "lon": "34.78",
        "neighborhood": "Florentin",
        "street": "Bialik",
        "house_number": "5",
    }
    parsed = _parse_row(row)
    assert parsed is not None
    assert parsed["city"] == "Tel Aviv"
    assert parsed["price"] == 2_500_000
    assert parsed["_geom_wkt"] == "SRID=4326;POINT(34.78 32.08)"


def test_parse_row_skips_bad():
    bad = {
        "deal_id": "100",
        "deal_date": "not-a-date",
        "city": "Tel Aviv",
        "property_type": "apartment",
        "rooms": "3",
        "sqm": "70",
        "price": "0",
        "lat": "32",
        "lon": "34",
    }
    assert _parse_row(bad) is None
