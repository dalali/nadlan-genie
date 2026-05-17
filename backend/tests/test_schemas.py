from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas import ScanRequest


def test_scan_request_defaults():
    r = ScanRequest(city="Ramat Gan", price_max=3_000_000)
    assert r.discount_threshold == 0.15
    assert r.max_pages == 3
    assert r.property_type == "apartment"


def test_scan_request_rejects_rooms_inverted():
    with pytest.raises(ValidationError):
        ScanRequest(city="X", rooms_min=5, rooms_max=2, price_max=1_000_000)


def test_scan_request_rejects_excess_pages():
    with pytest.raises(ValidationError):
        ScanRequest(city="X", price_max=1_000_000, max_pages=4)


def test_scan_request_rejects_zero_price():
    with pytest.raises(ValidationError):
        ScanRequest(city="X", price_max=0)


def test_scan_request_rejects_unknown_property_type():
    with pytest.raises(ValidationError):
        ScanRequest(city="X", price_max=1_000_000, property_type="land")
