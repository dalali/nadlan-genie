from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PropertyType = Literal["apartment", "garden_apartment", "penthouse", "private_house"]
ScanStatus = Literal["queued", "running", "done", "error"]
ScanStep = Literal["scrape", "normalize", "value", "rank"]
Confidence = Literal["high", "medium", "low"]


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    city: str = Field(..., min_length=1, max_length=64)
    rooms_min: float = Field(1, ge=1, le=10)
    rooms_max: float = Field(10, ge=1, le=10)
    price_max: int = Field(..., gt=0, le=50_000_000)
    discount_threshold: float = Field(0.15, ge=-1.0, le=1.0)
    max_pages: int = Field(3, ge=1, le=3)
    property_type: PropertyType = "apartment"

    @field_validator("rooms_max")
    @classmethod
    def _rooms_range(cls, v: float, info):
        rmin = info.data.get("rooms_min")
        if rmin is not None and v < rmin:
            raise ValueError("rooms_max must be >= rooms_min")
        return v


class ScanCreated(BaseModel):
    scan_id: uuid.UUID
    status: ScanStatus


class ListingOut(BaseModel):
    id: int
    url: str
    address: str | None
    neighborhood: str | None
    city: str
    rooms: float | None
    sqm: float | None
    price: int | None
    property_type: str | None


class ScanResultOut(BaseModel):
    rank: int
    listing: ListingOut
    asking_price: int
    estimated_value: int
    median_ppsqm: float
    discount_percent: float
    comparable_count: int
    radius_m: int
    confidence: Confidence


class SkippedItem(BaseModel):
    url: str
    reason: str


class ScanDetail(BaseModel):
    scan_id: uuid.UUID
    status: ScanStatus
    step: ScanStep | None = None
    filters: dict[str, Any]
    requested_at: datetime
    finished_at: datetime | None = None
    result_count: int | None = None
    error_msg: str | None = None
    results: list[ScanResultOut] = []
    skipped: list[SkippedItem] = []


class ScanListItem(BaseModel):
    scan_id: uuid.UUID
    requested_at: datetime
    finished_at: datetime | None
    status: ScanStatus
    city: str
    filters: dict[str, Any]
    result_count: int | None


class ScanList(BaseModel):
    scans: list[ScanListItem]


class HealthOut(BaseModel):
    status: str
    postgres: str
    transactions_loaded: int
    version: str


class CitiesOut(BaseModel):
    cities: list[str]


class ImportResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    total: int


class ImportByPath(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
