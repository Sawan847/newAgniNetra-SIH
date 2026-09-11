"""Pydantic schemas for Incident Alerts."""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AlertBase(BaseModel):
    hotspot_id: uuid.UUID
    prediction_id: Optional[uuid.UUID] = None
    severity: str = Field(..., description="critical, high, medium, low")
    alert_type: Optional[str] = None
    status: str = Field("active", description="active, acknowledged, resolved, false_positive")
    description: Optional[str] = None
    risk_score: Optional[float] = None
    assigned_to: Optional[uuid.UUID] = None
    assigned_analyst_name: Optional[str] = None
    acknowledged_at: Optional[datetime.datetime] = None
    acknowledged_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AlertCreate(AlertBase):
    pass


class AlertUpdate(BaseModel):
    status: Optional[str] = Field(None, description="active, acknowledged, resolved, false_positive")
    severity: Optional[str] = None
    description: Optional[str] = None
    assigned_to: Optional[uuid.UUID] = None
    assigned_analyst_name: Optional[str] = None
    acknowledged_by: Optional[str] = None
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime.datetime] = None


class AlertAssignRequest(BaseModel):
    assigned_analyst_name: str
    assigned_to: Optional[uuid.UUID] = None


class AlertResolveRequest(BaseModel):
    resolution_notes: str
    status: str = Field("resolved", description="resolved or false_positive")


class AlertRead(AlertBase):
    id: uuid.UUID
    created_at: datetime.datetime
    resolved_at: Optional[datetime.datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AlertListResponse(BaseModel):
    status: str = "success"
    data: List[AlertRead]
    meta: Dict[str, Any]
