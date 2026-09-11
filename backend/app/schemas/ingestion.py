"""Pydantic schemas for Ingestion endpoints."""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.services.geometry import validate_bbox
from app.services.firms import SUPPORTED_FIRMS_SOURCES


class FIRMSIngestRequest(BaseModel):
    bbox: Tuple[float, float, float, float] = Field(
        ...,
        description="Bounding box: (min_lon, min_lat, max_lon, max_lat)",
        example=[68.0, 6.0, 97.5, 37.5],  # India
    )
    start_date: datetime.date = Field(
        default_factory=datetime.date.today,
        description="Start acquisition date (YYYY-MM-DD)",
    )
    end_date: Optional[datetime.date] = Field(
        None,
        description="End acquisition date (YYYY-MM-DD). If omitted, defaults to start_date",
    )
    sources: Optional[List[str]] = Field(
        ["VIIRS_SNPP_NRT", "VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT"],
        description="List of FIRMS VIIRS satellite sensors to query",
    )

    @field_validator("bbox")
    @classmethod
    def valid_bbox(cls, value):
        return validate_bbox(value)

    @field_validator("sources")
    @classmethod
    def valid_sources(cls, value):
        if value is not None and (not value or any(s not in SUPPORTED_FIRMS_SOURCES for s in value)):
            raise ValueError("Select at least one supported FIRMS source")
        return list(dict.fromkeys(value)) if value else value

    @model_validator(mode="after")
    def valid_dates(self):
        end = self.end_date or self.start_date
        if end < self.start_date:
            raise ValueError("End date must be on or after start date")
        if end > datetime.datetime.now(datetime.timezone.utc).date():
            raise ValueError("Acquisition dates cannot be in the future")
        if (end - self.start_date).days > 90:
            raise ValueError("Import at most 91 days per run")
        return self


class OSMIngestRequest(BaseModel):
    bbox: Tuple[float, float, float, float]

    @field_validator("bbox")
    @classmethod
    def valid_bbox(cls, value):
        validate_bbox(value)
        if (value[2] - value[0]) * (value[3] - value[1]) > 4:
            raise ValueError("Use a regional OSM bounding box of at most 4 square degrees")
        return value


class IngestionRunRead(BaseModel):
    id: uuid.UUID
    source: str
    status: str
    records_fetched: int
    records_inserted: int
    records_skipped: int
    error_message: Optional[str] = None
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class FIRMSIngestResponse(BaseModel):
    status: str = "success"
    message: str
    run_id: uuid.UUID
    data: Optional[IngestionRunRead] = None
