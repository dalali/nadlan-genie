from __future__ import annotations

import io

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas import ImportByPath, ImportResult
from ..services.importer import import_csv, import_path

router = APIRouter(tags=["transactions"])


@router.post("/import-transactions", response_model=ImportResult)
async def import_transactions(
    file: UploadFile | None = File(default=None),
    body: ImportByPath | None = Body(default=None),
    db: Session = Depends(get_db),
) -> ImportResult:
    """Import transactions either from a multipart-uploaded CSV or a JSON `{path}` body."""
    if file is None and body is None:
        raise HTTPException(
            status_code=400,
            detail="Provide either a multipart `file` or JSON body `{\"path\": \"...\"}`.",
        )
    if file is not None:
        content = (await file.read()).decode("utf-8", errors="replace")
        try:
            stats = import_csv(io.StringIO(content), db)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    else:
        try:
            stats = import_path(body.path, db)  # type: ignore[union-attr]
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return ImportResult(**stats)
