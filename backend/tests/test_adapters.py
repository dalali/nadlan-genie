from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.adapters import RawListing, SampleAdapter, Yad2Adapter, get_adapter


@pytest.fixture()
def fixture_path(tmp_path: Path) -> Path:
    data = [
        {
            "id": 1,
            "city": "Tel Aviv",
            "url": "https://example.com/1",
            "address": "Bialik 1",
            "rooms": 3,
            "sqm": 70,
            "price": 2500000,
            "property_type": "apartment",
            "lat": 32.08,
            "lon": 34.78,
        },
        {
            "id": 2,
            "city": "Tel Aviv",
            "url": "https://example.com/2",
            "address": "Bialik 2",
            "rooms": 5,
            "sqm": 120,
            "price": 6000000,
            "property_type": "apartment",
            "lat": 32.08,
            "lon": 34.78,
        },
        {
            "id": 3,
            "city": "Haifa",
            "url": "https://example.com/3",
            "address": "Herzl 7",
            "rooms": 3,
            "sqm": 70,
            "price": 1500000,
            "property_type": "apartment",
            "lat": 32.79,
            "lon": 34.99,
        },
    ]
    p = tmp_path / "fixture.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_sample_adapter_filters_by_city_and_rooms(fixture_path: Path):
    adapter = SampleAdapter(str(fixture_path))
    results = asyncio.run(
        adapter.search(
            city="Tel Aviv",
            rooms_min=2,
            rooms_max=4,
            price_max=10_000_000,
            max_pages=3,
            property_type="apartment",
        )
    )
    assert len(results) == 1
    assert isinstance(results[0], RawListing)
    assert results[0].source_listing_id == "1"


def test_sample_adapter_filters_price(fixture_path: Path):
    adapter = SampleAdapter(str(fixture_path))
    results = asyncio.run(
        adapter.search(
            city="Tel Aviv",
            rooms_min=1,
            rooms_max=10,
            price_max=3_000_000,
            max_pages=3,
            property_type="apartment",
        )
    )
    assert [r.source_listing_id for r in results] == ["1"]


def test_sample_adapter_caps_results(fixture_path: Path):
    adapter = SampleAdapter(str(fixture_path))
    # max_pages=1 → cap = 20, but fixture only has 1 matching anyway.
    results = asyncio.run(
        adapter.search(
            city="Haifa",
            rooms_min=1,
            rooms_max=10,
            price_max=10_000_000,
            max_pages=1,
            property_type="apartment",
        )
    )
    assert len(results) == 1
    assert results[0].city == "Haifa"


def test_get_adapter_factory(monkeypatch, fixture_path: Path):
    monkeypatch.setenv("LISTING_SOURCE", "sample")
    monkeypatch.setenv("SAMPLE_LISTINGS_PATH", str(fixture_path))
    # Force reload of cached settings
    from app.config import get_settings

    get_settings.cache_clear()
    adapter = get_adapter()
    assert isinstance(adapter, SampleAdapter)


def test_get_adapter_unknown_raises(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LISTING_SOURCE", "nope")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        get_adapter()
    monkeypatch.setenv("LISTING_SOURCE", "sample")
    get_settings.cache_clear()


def test_yad2_unsupported_city_raises():
    """Adapter should raise ValueError for an unknown city."""
    adapter = Yad2Adapter(rate_limit_s=0)
    with pytest.raises(ValueError, match="not supported by Yad2 adapter"):
        asyncio.run(
            adapter.search(
                city="Atlantis",
                rooms_min=3,
                rooms_max=4,
                price_max=3_000_000,
                max_pages=1,
                property_type="apartment",
            )
        )


def test_yad2_api_failure_returns_empty(monkeypatch):
    """Adapter should return empty list when the HTTP call fails."""
    import requests.exceptions

    def _bad_fetch(url, params):
        raise requests.exceptions.ConnectionError("simulated failure")

    monkeypatch.setattr("app.adapters.yad2._fetch_page", _bad_fetch)

    adapter = Yad2Adapter(rate_limit_s=0)
    results = asyncio.run(
        adapter.search(
            city="tel aviv",
            rooms_min=3,
            rooms_max=4,
            price_max=3_000_000,
            max_pages=1,
            property_type="apartment",
        )
    )
    assert results == []


def test_yad2_parses_mock_response(monkeypatch):
    """Adapter should parse a realistic mock API response into RawListing objects."""
    mock_response = {
        "data": {
            "feed": {
                "total_pages": 1,
                "feed_items": [
                    {
                        "id": "abc123",
                        "link_token": "abc123",
                        "city_text": "תל אביב",
                        "neighborhood_text": "פלורנטין",
                        "street": "הרצל",
                        "house_num": "10",
                        "room_number": 3.5,
                        "square_meters": 80,
                        "price": 2_100_000,
                        "coordinates": {"latitude": 32.08, "longitude": 34.81},
                        "property_type_text": "דירה",
                    },
                    {
                        # Missing price — should be skipped
                        "id": "bad001",
                        "link_token": "bad001",
                        "city_text": "תל אביב",
                        "room_number": 3,
                        "square_meters": 70,
                        "price": None,
                        "coordinates": {},
                    },
                ],
            }
        }
    }

    def _mock_fetch(url, params):
        return mock_response

    monkeypatch.setattr("app.adapters.yad2._fetch_page", _mock_fetch)

    adapter = Yad2Adapter(rate_limit_s=0)
    results = asyncio.run(
        adapter.search(
            city="tel aviv",
            rooms_min=3,
            rooms_max=4,
            price_max=3_000_000,
            max_pages=1,
            property_type="apartment",
        )
    )

    assert len(results) == 1
    r = results[0]
    assert isinstance(r, RawListing)
    assert r.source == "yad2"
    assert r.source_listing_id == "abc123"
    assert r.url == "https://www.yad2.co.il/item/abc123"
    assert r.rooms == 3.5
    assert r.sqm == 80.0
    assert r.price == 2_100_000
    assert r.lat == 32.08
    assert r.lon == 34.81
