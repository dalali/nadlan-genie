from __future__ import annotations

from ..config import get_settings
from .base import ListingAdapter, RawListing
from .sample import SampleAdapter
from .yad2 import Yad2Adapter


def get_adapter(name: str | None = None) -> ListingAdapter:
    settings = get_settings()
    chosen = (name or settings.listing_source).lower()
    if chosen == "sample":
        return SampleAdapter(settings.sample_listings_path)
    if chosen == "yad2":
        return Yad2Adapter()
    raise ValueError(f"Unknown LISTING_SOURCE: {chosen!r}. Supported: sample, yad2.")


__all__ = ["ListingAdapter", "RawListing", "SampleAdapter", "Yad2Adapter", "get_adapter"]
