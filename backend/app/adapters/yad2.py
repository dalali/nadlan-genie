"""Yad2 adapter — scrapes live listings from Yad2.

Strategy (tried in order per page):
  1. Parse __NEXT_DATA__ JSON embedded in the search results HTML page.
  2. Fall back to the gw.yad2.co.il JSON API with session cookies.

Uses a persistent requests.Session so cookies are carried across requests,
which is required to avoid bot detection. Set LISTING_SOURCE=yad2 to activate.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from ..config import get_settings
from .base import ListingAdapter, RawListing

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# City ID mapping (Yad2 numeric IDs)
# ---------------------------------------------------------------------------
CITY_IDS: dict[str, str] = {
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
    "tel aviv": "5000",
    "jerusalem": "3000",
    "haifa": "4000",
    "ramat gan": "8600",
    "petah tikva": "7900",
    "rishon lezion": "8300",
    "netanya": "7400",
    "beer sheva": "1100",
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

PROPERTY_TYPE_MAP: dict[str, str] = {
    "apartment": "1",
    "דירה": "1",
    "garden_apartment": "3",
    "penthouse": "6",
    "cottage": "5",
    "villa": "4",
}

# Browser-realistic headers for page requests
_PAGE_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
}

# Headers for JSON API calls (after session is warmed up)
_API_HEADERS: dict[str, str] = {
    **_PAGE_HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.yad2.co.il/",
    "Origin": "https://www.yad2.co.il",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
}

try:
    import requests as _requests
    _REQUESTS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _requests = None  # type: ignore[assignment]
    _REQUESTS_AVAILABLE = False


def _make_session() -> Any:
    session = _requests.Session()
    session.headers.update(_PAGE_HEADERS)
    return session


def _warm_session(session: Any) -> None:
    """Visit the Yad2 homepage to acquire session cookies."""
    try:
        session.get("https://www.yad2.co.il/", timeout=15)
        logger.debug("Yad2 session warmed up, cookies: %s", list(session.cookies.keys()))
    except Exception as exc:
        logger.warning("Yad2 session warmup failed (continuing anyway): %s", exc)


def _search_url(city_id: str, rooms_min: float, rooms_max: float,
                price_max: int, prop_code: str, page: int) -> str:
    return (
        f"https://www.yad2.co.il/realestate/forsale"
        f"?city={city_id}&rooms={rooms_min}-{rooms_max}"
        f"&price=0-{price_max}&property={prop_code}&page={page}"
    )


def _api_url(city_id: str, rooms_min: float, rooms_max: float,
             price_max: int, prop_code: str, page: int) -> str:
    return (
        f"https://gw.yad2.co.il/feed-search-legacy/realestate/forsale"
        f"?city={city_id}&rooms={rooms_min}-{rooms_max}"
        f"&price=0-{price_max}&property={prop_code}&forceLdLoad=1&page={page}"
    )


def _extract_next_data(html: str) -> dict[str, Any]:
    """Pull the __NEXT_DATA__ JSON blob from a Next.js page."""
    m = re.search(
        r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html, re.S
    )
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def _items_from_next_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Navigate __NEXT_DATA__ to find feed_items. Yad2's structure varies."""
    paths = [
        ["props", "pageProps", "feed", "feed_items"],
        ["props", "pageProps", "initialData", "feed", "feed_items"],
        ["props", "pageProps", "data", "feed", "feed_items"],
        ["props", "pageProps", "listings"],
    ]
    for path in paths:
        node = data
        for key in path:
            if not isinstance(node, dict):
                break
            node = node.get(key)  # type: ignore[assignment]
        if isinstance(node, list) and node:
            logger.debug("Found %d items via __NEXT_DATA__ path: %s", len(node), path)
            return node
    return []


def _fetch_page_sync(session: Any, city_id: str, rooms_min: float, rooms_max: float,
                     price_max: int, prop_code: str, page: int) -> list[dict[str, Any]]:
    """Fetch one page of listings. Tries HTML __NEXT_DATA__ then JSON API."""

    # Strategy 1: parse __NEXT_DATA__ from the search results HTML
    page_url = _search_url(city_id, rooms_min, rooms_max, price_max, prop_code, page)
    try:
        resp = session.get(page_url, timeout=20)
        logger.debug("Yad2 HTML page %d: status %d url %s", page, resp.status_code, resp.url)
        if resp.status_code == 200:
            next_data = _extract_next_data(resp.text)
            if next_data:
                items = _items_from_next_data(next_data)
                if items:
                    return items
                logger.debug("__NEXT_DATA__ found but no items in known paths")
            else:
                logger.debug("No __NEXT_DATA__ in HTML response")
    except Exception as exc:
        logger.warning("Yad2 HTML fetch failed page %d: %s", page, exc)

    # Strategy 2: JSON API with session cookies
    api_url = _api_url(city_id, rooms_min, rooms_max, price_max, prop_code, page)
    try:
        resp = session.get(api_url, headers=_API_HEADERS, timeout=15)
        logger.debug("Yad2 API page %d: status %d", page, resp.status_code)
        if resp.status_code == 200:
            feed = resp.json().get("data", {}).get("feed", {})
            items = feed.get("feed_items", [])
            if items:
                return items
            logger.debug("Yad2 API returned 200 but no feed_items")
    except Exception as exc:
        logger.warning("Yad2 API fetch failed page %d: %s", page, exc)

    return []


class Yad2Adapter(ListingAdapter):
    name = "yad2"

    def __init__(self, rate_limit_s: float | None = None) -> None:
        self._rate_limit_s = (
            rate_limit_s if rate_limit_s is not None else get_settings().scrape_rate_limit_s
        )

    async def search(
        self,
        city: str,
        rooms_min: float,
        rooms_max: float,
        price_max: int,
        max_pages: int,
        property_type: str,
    ) -> list[RawListing]:
        if not _REQUESTS_AVAILABLE:
            raise RuntimeError("'requests' package is not installed.")

        city_id = self._resolve_city_id(city)
        prop_code = PROPERTY_TYPE_MAP.get(property_type.lower(), "1")
        loop = asyncio.get_event_loop()

        # Warm up session in thread pool (blocking I/O)
        session = await loop.run_in_executor(None, _make_session)
        await loop.run_in_executor(None, _warm_session, session)

        all_listings: list[RawListing] = []

        for page_num in range(1, max_pages + 1):
            items: list[dict[str, Any]] = await loop.run_in_executor(
                None, _fetch_page_sync,
                session, city_id, rooms_min, rooms_max, price_max, prop_code, page_num
            )

            if not items:
                logger.warning("Yad2: no items on page %d — stopping", page_num)
                break

            for item in items:
                listing = self._parse_item(item, city)
                if listing is not None:
                    all_listings.append(listing)

            logger.info(
                "Yad2 page %d — got %d items, total so far: %d",
                page_num, len(items), len(all_listings)
            )

            if page_num < max_pages:
                await asyncio.sleep(self._rate_limit_s)

        return all_listings

    def _resolve_city_id(self, city: str) -> str:
        key = city.strip().lower()
        city_id = CITY_IDS.get(key) or CITY_IDS.get(city.strip())
        if city_id is None:
            raise ValueError(
                f"City '{city}' not supported by Yad2 adapter. "
                f"Supported: {sorted(CITY_IDS.keys())}"
            )
        return city_id

    @staticmethod
    def _parse_item(item: dict[str, Any], city: str) -> RawListing | None:
        price = item.get("price")
        sqm = item.get("square_meters")
        if not price or not sqm:
            logger.debug("Skipping item %s — missing price or sqm", item.get("id", "?"))
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
