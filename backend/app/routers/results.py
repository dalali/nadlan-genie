from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..deps import get_db
from ..models import ScanRun
from ..schemas import ScanList, ScanListItem

router = APIRouter(tags=["results"])


@router.get("/results", response_model=ScanList)
def list_results(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
) -> ScanList:
    runs = (
        db.query(ScanRun)
        .order_by(ScanRun.requested_at.desc())
        .limit(limit)
        .all()
    )
    items = [
        ScanListItem(
            scan_id=r.id,
            requested_at=r.requested_at,
            finished_at=r.finished_at,
            status=r.status,  # type: ignore[arg-type]
            city=(r.filters_json or {}).get("city", ""),
            filters=r.filters_json or {},
            result_count=r.result_count,
        )
        for r in runs
    ]
    return ScanList(scans=items)
