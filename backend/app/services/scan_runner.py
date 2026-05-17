from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from ..adapters import RawListing, get_adapter
from ..db import SessionLocal
from ..geo import jittered_centroid
from ..logging_setup import get_logger
from ..models import Listing, ScanResult, ScanRun
from .valuation import value_listing

log = get_logger(__name__)

# Process-wide semaphore: only one scan runs at a time.
_scan_semaphore = asyncio.Semaphore(1)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize(raw: RawListing) -> tuple[dict[str, Any], str]:
    """Return (insert-dict, geom_wkt) ready for an upsert."""
    lat = raw.lat
    lon = raw.lon
    if lat is None or lon is None:
        lat, lon = jittered_centroid(raw.city, seed=hash(raw.source_listing_id) & 0xFFFFFFFF)
    geom_wkt = f"SRID=4326;POINT({lon} {lat})"
    return (
        {
            "source": raw.source,
            "source_listing_id": raw.source_listing_id,
            "city": raw.city,
            "neighborhood": raw.neighborhood,
            "address": raw.address,
            "rooms": raw.rooms,
            "sqm": raw.sqm,
            "price": raw.price,
            "property_type": raw.property_type,
            "url": raw.url,
            "raw_json": raw.raw_json,
        },
        geom_wkt,
    )


def _upsert_listings(raws: list[RawListing], db: Session) -> list[Listing]:
    """Upsert scraped listings and return ORM rows in input order."""
    ids: list[int] = []
    for raw in raws:
        data, geom_wkt = _normalize(raw)
        stmt = pg_insert(Listing).values(**data, geom=func.ST_GeomFromEWKT(geom_wkt))
        stmt = stmt.on_conflict_do_update(
            index_elements=["source", "source_listing_id"],
            set_={
                "city": stmt.excluded.city,
                "neighborhood": stmt.excluded.neighborhood,
                "address": stmt.excluded.address,
                "rooms": stmt.excluded.rooms,
                "sqm": stmt.excluded.sqm,
                "price": stmt.excluded.price,
                "property_type": stmt.excluded.property_type,
                "url": stmt.excluded.url,
                "raw_json": stmt.excluded.raw_json,
                "geom": stmt.excluded.geom,
                "scraped_at": func.now(),
            },
        ).returning(Listing.id)
        res = db.execute(stmt)
        new_id = res.scalar_one()
        ids.append(new_id)
    db.flush()
    if not ids:
        return []
    rows = db.query(Listing).filter(Listing.id.in_(ids)).all()
    by_id = {r.id: r for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def _update_run(db: Session, scan_id: uuid.UUID, **fields: Any) -> None:
    db.query(ScanRun).filter(ScanRun.id == scan_id).update(fields)
    db.commit()


async def run_scan(scan_id: uuid.UUID, filters: dict[str, Any]) -> None:
    """Execute a scan end-to-end. Errors are persisted to scan_runs and never propagated."""
    async with _scan_semaphore:
        log.info("scan.start", scan_id=str(scan_id), filters=filters)
        db = SessionLocal()
        try:
            _update_run(db, scan_id, status="running", step="scrape")

            adapter = get_adapter()
            raws = await adapter.search(
                city=filters["city"],
                rooms_min=filters["rooms_min"],
                rooms_max=filters["rooms_max"],
                price_max=filters["price_max"],
                max_pages=filters["max_pages"],
                property_type=filters["property_type"],
            )
            log.info("scan.scraped", scan_id=str(scan_id), count=len(raws))

            _update_run(db, scan_id, step="normalize")
            listings = _upsert_listings(raws, db)

            _update_run(db, scan_id, step="value")
            valued: list[tuple[Listing, Any]] = []
            skipped: list[dict[str, str]] = []
            for listing in listings:
                v = value_listing(listing, db)
                if v is None:
                    skipped.append({"url": listing.url, "reason": "insufficient_comparables"})
                    continue
                valued.append((listing, v))

            _update_run(db, scan_id, step="rank")
            threshold = float(filters.get("discount_threshold", 0.15))
            qualifying = [
                (listing, v) for (listing, v) in valued if v.discount_percent >= threshold
            ]
            qualifying.sort(key=lambda x: x[1].discount_percent, reverse=True)

            for below in [(l, v) for (l, v) in valued if v.discount_percent < threshold]:
                skipped.append({"url": below[0].url, "reason": "discount_below_threshold"})

            # Persist scan_results
            for rank, (listing, v) in enumerate(qualifying, start=1):
                db.add(
                    ScanResult(
                        scan_id=scan_id,
                        rank=rank,
                        listing_id=listing.id,
                        asking_price=int(listing.price or 0),
                        estimated_value=v.estimated_value,
                        median_ppsqm=v.median_ppsqm,
                        discount_percent=v.discount_percent,
                        comparable_count=v.comparable_count,
                        radius_m=v.radius_m,
                        confidence=v.confidence,
                    )
                )
            db.commit()

            _update_run(
                db,
                scan_id,
                status="done",
                step=None,
                finished_at=_now(),
                result_count=len(qualifying),
                skipped_json=skipped,
            )
            log.info(
                "scan.done",
                scan_id=str(scan_id),
                results=len(qualifying),
                skipped=len(skipped),
            )
        except Exception as exc:  # noqa: BLE001
            log.exception("scan.error", scan_id=str(scan_id))
            try:
                db.rollback()  # clear any aborted transaction before writing error status
                _update_run(
                    db,
                    scan_id,
                    status="error",
                    finished_at=_now(),
                    error_msg=f"{type(exc).__name__}: {exc}",
                )
            except Exception:  # noqa: BLE001
                pass
        finally:
            db.close()
