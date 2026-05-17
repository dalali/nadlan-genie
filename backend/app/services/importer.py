from __future__ import annotations

import csv
import io
from datetime import date, datetime
from pathlib import Path
from typing import IO, Any

from sqlalchemy import cast, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session
from sqlalchemy.types import Text

from ..config import get_settings
from ..db import SessionLocal
from ..logging_setup import get_logger
from ..models import Transaction

log = get_logger(__name__)

REQUIRED_COLUMNS = {
    "deal_id",
    "deal_date",
    "city",
    "property_type",
    "rooms",
    "sqm",
    "price",
    "lat",
    "lon",
}


def _parse_date(s: str) -> date:
    s = s.strip()
    # Try ISO first, then DD/MM/YYYY
    try:
        return date.fromisoformat(s)
    except ValueError:
        return datetime.strptime(s, "%d/%m/%Y").date()


def _parse_row(row: dict[str, str]) -> dict[str, Any] | None:
    try:
        lat = float(row["lat"])
        lon = float(row["lon"])
        price = int(float(row["price"]))
        if price <= 0:
            return None
        return {
            "deal_id": row["deal_id"].strip(),
            "deal_date": _parse_date(row["deal_date"]),
            "city": row["city"].strip(),
            "neighborhood": row.get("neighborhood", "").strip() or None,
            "street": row.get("street", "").strip() or None,
            "house_number": row.get("house_number", "").strip() or None,
            "property_type": row["property_type"].strip(),
            "rooms": float(row["rooms"]) if row.get("rooms") else None,
            "sqm": float(row["sqm"]) if row.get("sqm") else None,
            "price": price,
            "_geom_wkt": f"SRID=4326;POINT({lon} {lat})",
        }
    except (KeyError, ValueError) as exc:
        log.warning("importer.parse_skipped", error=str(exc), row=row)
        return None


def import_csv(fileobj: IO[str], db: Session, *, batch_size: int = 500) -> dict[str, int]:
    """Stream a CSV into the transactions table. Returns counts."""
    reader = csv.DictReader(fileobj)
    if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or [])
        raise ValueError(f"CSV is missing required columns: {sorted(missing)}")

    inserted = 0
    updated = 0
    skipped = 0
    total = 0

    batch: list[dict[str, Any]] = []

    def _flush(batch_to_flush: list[dict[str, Any]]) -> None:
        nonlocal inserted, updated
        if not batch_to_flush:
            return
        for item in batch_to_flush:
            wkt = item.pop("_geom_wkt")
            # Use ST_GeomFromEWKT so the SRID prefix in the WKT is honoured.
            stmt = pg_insert(Transaction).values(
                **item, geom=func.ST_GeomFromEWKT(wkt)
            )
            # Postgres xmax trick: on INSERT, the system column xmax is 0;
            # on UPDATE (i.e. ON CONFLICT DO UPDATE fired), xmax holds the
            # current transaction id (non-zero). Returning it lets us
            # distinguish inserted vs updated rows.
            stmt = stmt.on_conflict_do_update(
                index_elements=["deal_id", "deal_date"],
                set_={
                    "city": stmt.excluded.city,
                    "neighborhood": stmt.excluded.neighborhood,
                    "street": stmt.excluded.street,
                    "house_number": stmt.excluded.house_number,
                    "property_type": stmt.excluded.property_type,
                    "rooms": stmt.excluded.rooms,
                    "sqm": stmt.excluded.sqm,
                    "price": stmt.excluded.price,
                    "geom": stmt.excluded.geom,
                },
            ).returning(
                Transaction.id,
                cast(literal_column("xmax"), Text).label("xmax_text"),
            )
            res = db.execute(stmt)
            row = res.first()
            if row is not None:
                # xmax == '0' means the row was newly inserted; any other
                # value means the existing row was updated. Fall back to
                # treating the row as inserted if the driver/stub does not
                # expose xmax_text (e.g. unit-test fake sessions).
                xmax_val = getattr(row, "xmax_text", None)
                if xmax_val is None and hasattr(row, "_mapping"):
                    xmax_val = row._mapping.get("xmax_text")
                if xmax_val is not None and xmax_val != "0":
                    updated += 1
                else:
                    inserted += 1

    for row in reader:
        total += 1
        parsed = _parse_row(row)
        if parsed is None:
            skipped += 1
            continue
        batch.append(parsed)
        if len(batch) >= batch_size:
            _flush(batch)
            batch.clear()

    _flush(batch)
    db.commit()

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "total": total,
    }


# Directories from which `import_path` is allowed to read CSVs. Anything outside is rejected
# to prevent the JSON `{path: ...}` mode from being abused as a file-disclosure primitive
# (the API process can read e.g. /etc/passwd or /proc/<pid>/environ otherwise).
ALLOWED_IMPORT_ROOTS: tuple[str, ...] = ("/data", "/app/data")


def _is_under_allowed_root(p: Path) -> bool:
    try:
        resolved = p.resolve(strict=False)
    except (OSError, RuntimeError):
        return False
    return any(
        str(resolved).startswith(root.rstrip("/") + "/") or str(resolved) == root
        for root in ALLOWED_IMPORT_ROOTS
    )


def import_path(path: str | Path, db: Session) -> dict[str, int]:
    p = Path(path)
    if not _is_under_allowed_root(p):
        raise ValueError(
            f"Path {path!r} is outside the allowed roots {ALLOWED_IMPORT_ROOTS}. "
            "Place the CSV under /data (mounted from backend/data) or upload it as multipart."
        )
    if not p.exists():
        raise FileNotFoundError(f"CSV not found at {p}")
    if p.is_dir():
        raise ValueError(f"Path {path!r} is a directory, not a CSV file.")
    with p.open("r", encoding="utf-8") as f:
        return import_csv(f, db)


def transactions_count(db: Session) -> int:
    return int(db.execute(select(func.count(Transaction.id))).scalar_one() or 0)


def maybe_auto_seed() -> dict[str, int] | None:
    """Called on container startup. If AUTO_SEED=true and table is empty, import the bundled CSV.

    Safe to call repeatedly: it short-circuits when transactions already exist.
    """
    settings = get_settings()
    if not settings.auto_seed:
        log.info("seed.skipped", reason="AUTO_SEED=false")
        return None

    db = SessionLocal()
    try:
        existing = transactions_count(db)
        if existing > 0:
            log.info("seed.skipped", reason="non-empty", existing=existing)
            return None

        csv_path = settings.seed_csv_path
        if not Path(csv_path).exists():
            log.warning("seed.skipped", reason="csv-missing", path=csv_path)
            return None

        log.info("seed.start", path=csv_path)
        with open(csv_path, "r", encoding="utf-8") as f:
            stats = import_csv(f, db)
        log.info("seed.done", **stats)
        return stats
    finally:
        db.close()
