"""Yad2 adapter — DISABLED BY DEFAULT.

Enabling this adapter requires (a) installing Playwright chromium in the image and
(b) accepting that scraping may be blocked at any time. The default `sample` adapter
satisfies the MVP demo without any anti-bot interaction.
"""
from __future__ import annotations

import asyncio

from ..config import get_settings
from .base import ListingAdapter, RawListing


class Yad2Adapter(ListingAdapter):
    name = "yad2"

    def __init__(self, rate_limit_s: float | None = None) -> None:
        self._rate_limit_s = rate_limit_s or get_settings().scrape_rate_limit_s

    async def search(
        self,
        city: str,
        rooms_min: float,
        rooms_max: float,
        price_max: int,
        max_pages: int,
        property_type: str,
    ) -> list[RawListing]:
        # Intentionally a stub. Implementing this requires Playwright + maintenance against the
        # live Yad2 DOM, which is out of scope for the MVP. The shape below describes how a real
        # implementation would look.
        #
        # 1. Build a search URL from filters.
        # 2. For page in range(max_pages):
        #       async with rate_limited(self._rate_limit_s):
        #           html = await playwright_get(url, page=page)
        #       items = parse(html)
        #       results.extend(items)
        # 3. Return results.
        raise NotImplementedError(
            "Yad2 adapter is a stub. Implement with Playwright and rebuild the backend image with "
            "playwright + chromium installed, or set LISTING_SOURCE=sample (default)."
        )

    async def _sleep(self) -> None:
        await asyncio.sleep(self._rate_limit_s)
