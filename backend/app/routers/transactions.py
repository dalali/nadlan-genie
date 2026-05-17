from __future__ import annotations

import codecs
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile
from sqlalchemy.orm import Session

from ..deps import get_db
from ..schemas import ImportByPath, ImportResult
from ..services.importer import import_csv, import_path

router = APIRouter(tags=["transactions"])


async def _stream_to_tempfile(upload: UploadFile, chunk_size: int = 64 * 1024) -> str:
    """Spool an UploadFile to a temp file on disk and return the path.

    Avoids loading the whole CSV into RAM (US-4 acceptance criterion).
    """
    fd, path = tempfile.mkstemp(prefix="nadlan_import_", suffix=".csv")
    try:
        with os.fdopen(fd, "wb") as out:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
        return path
    except Exception:
        try:
            os.unlink(path)
        except OSError:
            pass
        raise


@router.post("/import-transactions", response_model=ImportResult)
async def import_transactions(
    request: Request,
    db: Session = Depends(get_db),
) -> ImportResult:
    """Import transactions either from a multipart-uploaded CSV or a JSON `{path}` body.

    The endpoint dispatches on Content-Type so we never try to apply both parsers to one body.
    """
    content_type = (request.headers.get("content-type") or "").lower()

    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        upload = form.get("file")
        if not isinstance(upload, UploadFile):
            raise HTTPException(
                status_code=400,
                detail="Multipart upload requires a `file` field.",
            )
        tmp_path = await _stream_to_tempfile(upload)
        try:
            with codecs.open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
                stats = import_csv(f, db)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return ImportResult(**stats)

    if content_type.startswith("application/json"):
        try:
            payload = await request.json()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON: {exc}") from exc
        try:
            body = ImportByPath.model_validate(payload)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        try:
            stats = import_path(body.path, db)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ImportResult(**stats)

    raise HTTPException(
        status_code=400,
        detail=(
            "Provide a multipart upload with field `file` (Content-Type: multipart/form-data) "
            "or a JSON body `{\"path\": \"...\"}` (Content-Type: application/json)."
        ),
    )
