from __future__ import annotations

import random
from typing import Tuple

# Approximate WGS84 centroids for supported Israeli cities.
CITY_CENTROIDS: dict[str, Tuple[float, float]] = {
    "Tel Aviv": (32.0853, 34.7818),
    "Ramat Gan": (32.0823, 34.8147),
    "Haifa": (32.7940, 34.9896),
    "Jerusalem": (31.7683, 35.2137),
    "Petah Tikva": (32.0871, 34.8878),
    "Holon": (32.0167, 34.7795),
    "Bat Yam": (32.0233, 34.7503),
    "Rishon LeZion": (31.9596, 34.8047),
    "Netanya": (32.3215, 34.8532),
    "Ashdod": (31.7949, 34.6493),
    "Beer Sheva": (31.2530, 34.7915),
}

SUPPORTED_CITIES = sorted(CITY_CENTROIDS.keys())


def jittered_centroid(city: str, *, seed: int | None = None) -> Tuple[float, float]:
    """Return (lat, lon) near the city centroid with ~500m jitter.

    Used only for listings the adapter could not geocode. Deterministic if seed given.
    """
    base = CITY_CENTROIDS.get(city, CITY_CENTROIDS["Tel Aviv"])
    rng = random.Random(seed)
    lat = base[0] + rng.gauss(0, 0.005)
    lon = base[1] + rng.gauss(0, 0.005)
    return lat, lon


def wkt_point(lat: float, lon: float) -> str:
    """WGS84 point in WKT (POINT lon lat). Note PostGIS expects 'POINT(lon lat)'."""
    return f"POINT({lon} {lat})"
