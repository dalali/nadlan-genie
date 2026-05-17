"""Pure-Python tests for the median-trim helper that powers valuation.

These avoid any DB dependency so they run in any environment.
"""
from __future__ import annotations

import statistics

from app.services.valuation import _trimmed_median


def test_trimmed_median_basic():
    assert _trimmed_median([1, 2, 3, 4, 5]) == statistics.median([1, 2, 3, 4, 5])


def test_trimmed_median_drops_extremes():
    # With trim_frac=0.05 on 100 items, drops top and bottom 5 each → median of middle 90.
    values = list(range(1, 101))  # 1..100
    # Insert wild outliers — they should be discarded by the 5% trim.
    values_with_outliers = [-1_000_000] * 5 + values[5:-5] + [1_000_000] * 5
    assert _trimmed_median(values_with_outliers, trim_frac=0.05) == statistics.median(
        values[5:-5]
    )


def test_trimmed_median_short_list_no_trim():
    # Too short to trim → returns plain median.
    assert _trimmed_median([10, 20, 30], trim_frac=0.05) == 20


def test_trimmed_median_single_item():
    assert _trimmed_median([42.0]) == 42.0
