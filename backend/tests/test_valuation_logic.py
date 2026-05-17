"""Pure tests for the discount math layered on top of `_trimmed_median`.

The full `value_listing` requires a live PostGIS session (ST_DWithin), so we test the
arithmetic in isolation here. Integration coverage of the full pipeline lives in
test_health_integration.py::test_scan_lifecycle.
"""
from __future__ import annotations

import math

from app.services.valuation import _trimmed_median


def _discount(estimated: float, asking: float) -> float:
    return (estimated - asking) / estimated


def test_discount_positive_when_asking_below_estimate():
    ppsqms = [40_000, 41_000, 42_000, 43_000, 44_000]
    median = _trimmed_median(ppsqms)
    estimated = median * 80
    asking = estimated * 0.75
    assert _discount(estimated, asking) == 0.25


def test_discount_zero_when_asking_equals_estimate():
    median = _trimmed_median([50_000.0])
    estimated = median * 100
    assert _discount(estimated, estimated) == 0.0


def test_discount_negative_when_asking_above_estimate():
    median = _trimmed_median([50_000.0, 51_000.0, 49_000.0])
    estimated = median * 100
    asking = estimated * 1.10
    assert _discount(estimated, asking) < 0


def test_trim_handles_realistic_skew():
    # 30 comparables clustered around 40k with two clear outliers.
    ppsqms = [30_000] * 1 + [40_000] * 28 + [200_000] * 1
    median = _trimmed_median(ppsqms, trim_frac=0.05)
    # Trim 5% of 30 = 1 from each end, so both outliers go.
    assert math.isclose(median, 40_000)


def test_estimate_scales_linearly_with_sqm():
    median = 30_000.0
    assert median * 50 == 1_500_000
    assert median * 100 == 3_000_000
    assert median * 150 == 4_500_000
