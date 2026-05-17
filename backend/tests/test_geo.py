"""Pure tests for the geo helpers — no DB or network required."""
from __future__ import annotations

import pytest

from app.geo import CITY_CENTROIDS, SUPPORTED_CITIES, jittered_centroid, wkt_point


def test_supported_cities_covers_prd_top_four():
    # PRD §15 names Tel Aviv, Ramat Gan, Haifa, Jerusalem as the sample data set.
    for required in ("Tel Aviv", "Ramat Gan", "Haifa", "Jerusalem"):
        assert required in SUPPORTED_CITIES, f"{required!r} missing from SUPPORTED_CITIES"


def test_supported_cities_sorted():
    assert SUPPORTED_CITIES == sorted(SUPPORTED_CITIES)


def test_jittered_centroid_deterministic_with_seed():
    a = jittered_centroid("Tel Aviv", seed=42)
    b = jittered_centroid("Tel Aviv", seed=42)
    assert a == b


def test_jittered_centroid_close_to_base():
    lat0, lon0 = CITY_CENTROIDS["Tel Aviv"]
    lat, lon = jittered_centroid("Tel Aviv", seed=1)
    # within ~5 km box (10 std deviations of 0.005°) — way more than enough.
    assert abs(lat - lat0) < 0.05
    assert abs(lon - lon0) < 0.05


def test_jittered_centroid_unknown_city_falls_back_to_tel_aviv():
    # Unknown cities should not raise — they map to Tel Aviv centroid (documented choice).
    lat_ta, lon_ta = CITY_CENTROIDS["Tel Aviv"]
    lat, lon = jittered_centroid("Atlantis", seed=7)
    assert abs(lat - lat_ta) < 0.05
    assert abs(lon - lon_ta) < 0.05


def test_wkt_point_format_is_lon_lat():
    # PostGIS expects POINT(lon lat); guard against the easy mistake of swapping them.
    assert wkt_point(32.08, 34.78) == "POINT(34.78 32.08)"


@pytest.mark.parametrize("city", list(CITY_CENTROIDS.keys()))
def test_all_centroids_are_in_israel(city: str):
    lat, lon = CITY_CENTROIDS[city]
    # Rough Israel bounding box.
    assert 29.0 < lat < 33.5, f"{city} latitude out of Israel"
    assert 34.0 < lon < 36.0, f"{city} longitude out of Israel"
