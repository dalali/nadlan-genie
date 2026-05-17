from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawListing:
    """An item returned by a listing adapter. May be missing fields; the normaliser fills gaps."""

    source: str
    source_listing_id: str
    city: str
    url: str
    address: str | None = None
    neighborhood: str | None = None
    rooms: float | None = None
    sqm: float | None = None
    price: int | None = None
    property_type: str | None = None
    lat: float | None = None
    lon: float | None = None
    raw_json: dict[str, Any] = field(default_factory=dict)


class ListingAdapter(ABC):
    """Source-agnostic listing scraper interface."""

    name: str = "abstract"

    @abstractmethod
    async def search(
        self,
        city: str,
        rooms_min: float,
        rooms_max: float,
        price_max: int,
        max_pages: int,
        property_type: str,
    ) -> list[RawListing]:
        """Return up to ~50 listings matching the filters."""
