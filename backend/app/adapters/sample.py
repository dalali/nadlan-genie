from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .base import ListingAdapter, RawListing


class SampleAdapter(ListingAdapter):
    """File-backed adapter that reads a bundled JSON fixture.

    The fixture is a list of dicts with the same keys as RawListing.
    """

    name = "sample"

    def __init__(self, fixture_path: str) -> None:
        self._path = Path(fixture_path)

    async def search(
        self,
        city: str,
        rooms_min: float,
        rooms_max: float,
        price_max: int,
        max_pages: int,
        property_type: str,
    ) -> list[RawListing]:
        if not self._path.exists():
            return []
        data: list[dict[str, Any]] = json.loads(self._path.read_text(encoding="utf-8"))

        results: list[RawListing] = []
        for item in data:
            if item.get("city") != city:
                continue
            if property_type and item.get("property_type") != property_type:
                continue
            rooms = item.get("rooms")
            if rooms is None or rooms < rooms_min or rooms > rooms_max:
                continue
            price = item.get("price")
            if price is None or price > price_max:
                continue
            results.append(
                RawListing(
                    source="sample",
                    source_listing_id=str(item["id"]),
                    city=item["city"],
                    url=item["url"],
                    address=item.get("address"),
                    neighborhood=item.get("neighborhood"),
                    rooms=float(rooms),
                    sqm=float(item["sqm"]) if item.get("sqm") is not None else None,
                    price=int(price),
                    property_type=item.get("property_type"),
                    lat=item.get("lat"),
                    lon=item.get("lon"),
                    raw_json=item,
                )
            )

        # Cap at max_pages * ~20 listings to mimic real pagination.
        cap = max_pages * 20
        return results[:cap]
