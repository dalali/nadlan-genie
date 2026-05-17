"""Yad2 adapter — fetches live listings from Yad2's undocumented JSON API.

Uses plain `requests` (no Playwright). Set LISTING_SOURCE=yad2 to activate.
Rate limiting between pages is controlled by SCRAPE_RATE_LIMIT_S (default 3 s).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..config import get_settings
from .base import ListingAdapter, RawListing

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# City ID mapping (Yad2 numeric IDs)
# ---------------------------------------------------------------------------
CITY_IDS: dict[str, str] = {
    # Hebrew names
    "תל אביב": "5000",
    "ירושלים": "3000",
    "חיפה": "4000",
    "רמת גן": "8600",
    "פתח תקווה": "7900",
    "ראשון לציון": "8300",
    "נתניה": "7400",
    "באר שבע": "1100",
    "אשדוד": "70",
    "חולון": "6200",
    "בת ים": "6100",
    "בני ברק": "6300",
    "רחובות": "8400",
    "הרצליה": "6600",
    "גבעתיים": "6700",
    "כפר סבא": "7100",
    "רעננה": "8200",
    "מודיעין": "7900",
    # English transliterations
    "tel aviv": "5000",
    "jerusalem": "3000",
    "haifa": "4000",
    "ramat gan": "8600",
    "petah tikva": "7900",
    "rishon lezion": "8300",
    "netanya": "7400",
    "beer sheva": "8200",  # note: IDs are approximate per spec
    "ashdod": "70",
    "holon": "6200",
    "bat yam": "6100",
    "bnei brak": "6300",
    "rehovot": "8400",
    "herzliya": "6600",
    "givatayim": "6700",
    "kfar saba": "7100",
    "raanana": "8200",
    "modiin": "7900",
}

# ---------------------------------------------------------------------------
# Property type mapping
# ---------------------------------------------------------------------------
PROPERTY_TYPE_MAP: dict[str, str] = {
    "apartment": "1",
    "דירה": "1",
    "garden_apartment": "3",
    "penthouse": "6",
    "cottage": "5",
    "villa": "4",
}

# ---------------------------------------------------------------------------
# HTTP headers to avoid immediate 403
# ---------------------------------------------------------------------------
_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.yad2.co.il/",
    "Origin": "https://www.yad2.co.il",
}

# ---------------------------------------------------------------------------
# Lazy import of requests so the module still loads when requests is absent
# ---------------------------------------------------------------------------
try:
    import requests as _requests
    import requests.exceptions as _req_exc

    _REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _requests = None  # type: ignore[assignment]
    _req_exc = None  # type: ignore[assignment]
    _REQUESTS_AVAILABLE = False


def _fetch_page(url: str, params: dict[str, str]) -> dict[str, Any]:
    """Synchronous HTTP GET; returns parsed JSON or raises requests.exceptions.*."""
    if not _REQUESTS_AVAILABLE:
        raise RuntimeError(
            "The 'requests' package is not installed. "
            "Run `pip install requests` or add it to requirements.txt."
        )
    response = _requests.get(url, params=params, headers=_HEADERS, timeout=15)
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


class Yad2Adapter(ListingAdapter):
    """Adapter that queries the Yad2 feed-search-legacy JSON API."""

    name = "yad2"
    BASE_URL = "https://gw.yad2.co.il/feed-search-legacy/realestate/forsale"

    def __init__(self, rate_limit_s: float | None = None) -> None:
        self._rate_limit_s = rate_limit_s if rate_limit_s is not None else get_settings().scrape_rate_limit_s

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search(
        self,
        city: str,
        rooms_min: float,
        rooms_max: float,
        price_max: int,
        max_pages: int,
        property_type: str,
    ) -> list[RawListing]:
        """Fetch listings from Yad2, paginating up to *max_pages* pages.

        Raises:
            ValueError: if *city* is not in the known city-ID mapping.
        """
        city_id = self._resolve_city_id(city)
        prop_code = PROPERTY_TYPE_MAP.get(property_type.lower(), "1")

        base_params: dict[str, str] = {
            "city": city_id,
            "rooms": f"{rooms_min}-{rooms_max}",
            "price": f"0-{price_max}",
            "forceLdLoad": "1",
            "property": prop_code,
        }

        all_listings: list[RawListing] = []
        loop = asyncio.get_event_loop()

        for page_num in range(1, max_pages + 1):
            params = {**base_params, "page": str(page_num)}

            try:
                data: dict[str, Any] = await loop.run_in_executor(
                    None, _fetch_page, self.BASE_URL, params
                )
            except Exception as exc:
                logger.warning(
                    "Yad2 API request failed on page %d: %s", page_num, exc
                )
                break

            feed = data.get("data", {}).get("feed", {})
            feed_items: list[dict[str, Any]] = feed.get("feed_items", [])
            total_pages: int = int(feed.get("total_pages", 1))

            for item in feed_items:
                listing = self._parse_item(item, city)
                if listing is not None:
                    all_listings.append(listing)

            logger.debug(
                "Yad2 page %d/%d — fetched %d items (total so far: %d)",
                page_num,
                total_pages,
                len(feed_items),
                len(all_listings),
            )

            if page_num >= total_pages:
                break

            # Rate-limit between pages (not after the last page)
            await asyncio.sleep(self._rate_limit_s)

        return all_listings

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _resolve_city_id(self, city: str) -> str:
        """Return the Yad2 numeric city ID, or raise ValueError."""
        key = city.strip().lower()
        # Try case-insensitive lookup first
        city_id = CITY_IDS.get(key) or CITY_IDS.get(city.strip())
        if city_id is None:
            raise ValueError(
                f"City '{city}' not supported by Yad2 adapter. "
                f"Supported: {sorted(CITY_IDS.keys())}"
            )
        return city_id

    @staticmethod
    def _parse_item(item: dict[str, Any], city: str) -> RawListing | None:
        """Convert a single feed_item dict to RawListing; return None if critical fields missing."""
        price = item.get("price")
        sqm = item.get("square_meters")

        if not price or not sqm:
            logger.debug(
                "Skipping Yad2 item %s — missing price or sqm",
                item.get("id", "<no-id>"),
            )
            return None

        listing_id = str(item.get("id", ""))
        link_token = item.get("link_token") or listing_id
        url = f"https://www.yad2.co.il/item/{link_token}"

        street = item.get("street", "")
        house_num = item.get("house_num", "")
        address = f"{street} {house_num}".strip() if street else None

        coords = item.get("coordinates") or {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")

        return RawListing(
            source="yad2",
            source_listing_id=listing_id,
            city=item.get("city_text") or city,
            url=url,
            address=address,
            neighborhood=item.get("neighborhood_text"),
            rooms=float(item["room_number"]) if item.get("room_number") is not None else None,
            sqm=float(sqm),
            price=int(price),
            property_type=item.get("property_type_text"),
            lat=float(lat) if lat is not None else None,
            lon=float(lon) if lon is not None else None,
            raw_json=item,
        )
