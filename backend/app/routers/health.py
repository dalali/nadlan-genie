from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import __version__
from ..deps import get_db
from ..models import Transaction
from ..schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    try:
        count = db.execute(select(func.count(Transaction.id))).scalar_one()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "postgres": "unreachable", "error": str(exc)},
        ) from exc
    return HealthOut(
        status="ok",
        postgres="ok",
        transactions_loaded=int(count),
        version=__version__,
    )
