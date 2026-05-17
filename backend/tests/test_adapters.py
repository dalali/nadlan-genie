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


def test_yad2_adapter_stub_raises():
    adapter = Yad2Adapter()
    with pytest.raises(NotImplementedError):
        asyncio.run(
            adapter.search(
                city="Tel Aviv",
                rooms_min=3,
                rooms_max=4,
                price_max=3_000_000,
                max_pages=1,
                property_type="apartment",
            )
        )
