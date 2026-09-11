"""Pydantic schemas for Monitoring Zones."""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ZoneBase(BaseModel):
    name: str = Field(..., max_length=255)
    description: Optional[str] = None
    min_lat: float = Field(..., ge=-90.0, le=90.0)
    max_lat: float = Field(..., ge=-90.0, le=90.0)
    min_lon: float = Field(..., ge=-180.0, le=180.0)
    max_lon: float = Field(..., ge=-180.0, le=180.0)
    sensitivity: str = Field("normal", description="critical, high, normal")
    alert_email: Optional[str] = None
    is_active: bool = True


class ZoneCreate(ZoneBase):
    pass


class ZoneRead(ZoneBase):
    id: uuid.UUID
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ZoneListResponse(BaseModel):
    status: str = "success"
    data: List[ZoneRead]
    meta: Dict[str, Any]
