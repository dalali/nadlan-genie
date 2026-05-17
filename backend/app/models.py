from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    deal_id: Mapped[str] = mapped_column(Text, nullable=False)
    deal_date: Mapped[date] = mapped_column(Date, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    neighborhood: Mapped[str | None] = mapped_column(Text)
    street: Mapped[str | None] = mapped_column(Text)
    house_number: Mapped[str | None] = mapped_column(Text)
    property_type: Mapped[str] = mapped_column(Text, nullable=False)
    rooms: Mapped[float | None] = mapped_column(Numeric(3, 1))
    sqm: Mapped[float | None] = mapped_column(Numeric(7, 2))
    price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    __table_args__ = (
        UniqueConstraint("deal_id", "deal_date", name="transactions_deal_unique"),
        Index("transactions_geom_gix", "geom", postgresql_using="gist"),
        Index("transactions_city_rooms_date_idx", "city", "rooms", "deal_date"),
    )


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_listing_id: Mapped[str] = mapped_column(Text, nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    neighborhood: Mapped[str | None] = mapped_column(Text)
    address: Mapped[str | None] = mapped_column(Text)
    rooms: Mapped[float | None] = mapped_column(Numeric(3, 1))
    sqm: Mapped[float | None] = mapped_column(Numeric(7, 2))
    price: Mapped[int | None] = mapped_column(Numeric(12, 0))
    property_type: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    raw_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326))
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("source", "source_listing_id", name="listings_source_unique"),
        Index("listings_geom_gix", "geom", postgresql_using="gist"),
    )


class ScanRun(Base):
    __tablename__ = "scan_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # queued|running|done|error
    step: Mapped[str | None] = mapped_column(String(32))
    error_msg: Mapped[str | None] = mapped_column(Text)
    filters_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_count: Mapped[int | None] = mapped_column(Integer)
    skipped_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB)

    results: Mapped[list["ScanResult"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan"
    )


class ScanResult(Base):
    __tablename__ = "scan_results"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_runs.id", ondelete="CASCADE"),
        primary_key=True,
    )
    rank: Mapped[int] = mapped_column(Integer, primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    asking_price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    estimated_value: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    median_ppsqm: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    discount_percent: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    comparable_count: Mapped[int] = mapped_column(Integer, nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)

    scan: Mapped[ScanRun] = relationship(back_populates="results")
    listing: Mapped[Listing] = relationship()

    __table_args__ = (
        Index("scan_results_scan_idx", "scan_id"),
    )
