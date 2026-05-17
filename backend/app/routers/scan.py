from __future__ import annotations

import asyncio
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db
from ..logging_setup import get_logger
from ..models import Listing, ScanResult, ScanRun
from ..schemas import (
    ListingOut,
    ScanCreated,
    ScanDetail,
    ScanRequest,
    ScanResultOut,
    SkippedItem,
)
from ..services.scan_runner import run_scan

log = get_logger(__name__)

router = APIRouter(tags=["scan"])


@router.post("/scan", response_model=ScanCreated, status_code=202)
def create_scan(payload: ScanRequest, db: Session = Depends(get_db)) -> ScanCreated:
    filters = payload.model_dump()
    scan = ScanRun(
        id=uuid.uuid4(),
        status="queued",
        filters_json=filters,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)
    # Schedule the actual work on the event loop. We do not use FastAPI BackgroundTasks because we
    # want to detach from the request lifecycle entirely.
    asyncio.create_task(run_scan(scan.id, filters))
    return ScanCreated(scan_id=scan.id, status="queued")


@router.get("/scan/{scan_id}", response_model=ScanDetail)
def get_scan(scan_id: uuid.UUID, db: Session = Depends(get_db)) -> ScanDetail:
    scan = db.get(ScanRun, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")

    results: list[ScanResultOut] = []
    if scan.status == "done":
        rows = (
            db.query(ScanResult, Listing)
            .join(Listing, Listing.id == ScanResult.listing_id)
            .filter(ScanResult.scan_id == scan_id)
            .order_by(ScanResult.rank.asc())
            .all()
        )
        for sr, listing in rows:
            results.append(
                ScanResultOut(
                    rank=sr.rank,
                    listing=ListingOut(
                        id=listing.id,
                        url=listing.url,
                        address=listing.address,
                        neighborhood=listing.neighborhood,
                        city=listing.city,
                        rooms=float(listing.rooms) if listing.rooms is not None else None,
                        sqm=float(listing.sqm) if listing.sqm is not None else None,
                        price=int(listing.price) if listing.price is not None else None,
                        property_type=listing.property_type,
                    ),
                    asking_price=int(sr.asking_price),
                    estimated_value=int(sr.estimated_value),
                    median_ppsqm=float(sr.median_ppsqm),
                    discount_percent=float(sr.discount_percent),
                    comparable_count=int(sr.comparable_count),
                    radius_m=int(sr.radius_m),
                    confidence=sr.confidence,  # type: ignore[arg-type]
                )
            )

    skipped: list[SkippedItem] = []
    if scan.skipped_json:
        skipped = [SkippedItem(**item) for item in scan.skipped_json]

    return ScanDetail(
        scan_id=scan.id,
        status=scan.status,  # type: ignore[arg-type]
        step=scan.step,  # type: ignore[arg-type]
        filters=scan.filters_json,
        requested_at=scan.requested_at,
        finished_at=scan.finished_at,
        result_count=scan.result_count,
        error_msg=scan.error_msg,
        results=results,
        skipped=skipped,
    )


@router.delete("/scan/{scan_id}")
def cancel_scan(scan_id: uuid.UUID, db: Session = Depends(get_db)) -> dict[str, str]:
    """Best-effort cancellation. Marks the run as errored if still in flight.

    Note: the in-progress asyncio.Task is not actually cancelled in MVP; the scan finishes its
    current step and writes its own status. This endpoint is a UX courtesy.
    """
    scan = db.get(ScanRun, scan_id)
    if scan is None:
        raise HTTPException(status_code=404, detail="scan not found")
    if scan.status in ("done", "error"):
        return {"status": scan.status}
    scan.status = "error"
    scan.error_msg = "cancelled"
    db.commit()
    return {"status": "cancelled"}
