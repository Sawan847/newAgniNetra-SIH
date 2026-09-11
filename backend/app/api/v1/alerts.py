"""Incident Alerts API endpoints."""

from __future__ import annotations

import datetime
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.events import broadcaster
from app.models.alert import Alert
from app.schemas.alert import (
    AlertAssignRequest,
    AlertCreate,
    AlertListResponse,
    AlertRead,
    AlertResolveRequest,
    AlertUpdate,
)

router = APIRouter()


def _to_alert_read(r: Alert) -> AlertRead:
    """Helper to convert Alert ORM object to Pydantic schema."""
    return AlertRead(
        id=r.id,
        hotspot_id=r.hotspot_id,
        prediction_id=r.prediction_id,
        severity=r.severity,
        alert_type=r.alert_type,
        status=r.status,
        description=r.description,
        risk_score=r.risk_score,
        assigned_to=r.assigned_to,
        assigned_analyst_name=r.assigned_analyst_name,
        acknowledged_at=r.acknowledged_at,
        acknowledged_by=r.acknowledged_by,
        resolution_notes=r.resolution_notes,
        metadata=r.metadata_,
        created_at=r.created_at,
        resolved_at=r.resolved_at,
    )


@router.get(
    "/alerts",
    response_model=AlertListResponse,
    summary="List operational incident alerts with severity and status filters",
)
def list_alerts(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    status: Optional[str] = Query(None, description="active, acknowledged, resolved, false_positive"),
    severity: Optional[str] = Query(None, description="critical, high, medium, low"),
    db: Session = Depends(get_db),
):
    """Retrieve paginated active and historical alerts."""
    query = db.query(Alert)
    if status:
        query = query.filter(Alert.status == status)
    if severity:
        query = query.filter(Alert.severity == severity)

    total = query.count()
    rows = query.order_by(desc(Alert.created_at)).offset((page - 1) * per_page).limit(per_page).all()

    return AlertListResponse(
        status="success",
        data=[_to_alert_read(r) for r in rows],
        meta={"total": total, "page": page, "per_page": per_page},
    )


@router.post(
    "/alerts",
    response_model=AlertRead,
    status_code=201,
    summary="Create a new manual or automated operational alert",
)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    """Create a new incident alert."""
    alert_obj = Alert(
        id=uuid.uuid4(),
        hotspot_id=payload.hotspot_id,
        prediction_id=payload.prediction_id,
        severity=payload.severity,
        alert_type=payload.alert_type,
        status=payload.status or "active",
        description=payload.description,
        risk_score=payload.risk_score,
        assigned_to=payload.assigned_to,
        assigned_analyst_name=payload.assigned_analyst_name,
        metadata_=payload.metadata,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(alert_obj)
    db.commit()
    db.refresh(alert_obj)
    broadcaster.publish("alert_raised", {"alert_id": str(alert_obj.id)})
    return _to_alert_read(alert_obj)


@router.post(
    "/alerts/{alert_id}/assign",
    response_model=AlertRead,
    summary="Assign an alert to a specific analyst",
)
def assign_alert(
    alert_id: uuid.UUID,
    payload: AlertAssignRequest,
    db: Session = Depends(get_db),
):
    """Assign incident alert to an operations analyst for investigation."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.assigned_to = payload.assigned_to
    alert.assigned_analyst_name = payload.assigned_analyst_name
    if alert.status == "active":
        alert.status = "acknowledged"
        alert.acknowledged_at = datetime.datetime.now(datetime.timezone.utc)
        alert.acknowledged_by = payload.assigned_analyst_name

    db.commit()
    db.refresh(alert)
    broadcaster.publish("alert_updated", {"alert_id": str(alert.id)})
    return _to_alert_read(alert)


@router.post(
    "/alerts/{alert_id}/resolve",
    response_model=AlertRead,
    summary="Resolve an alert with notes",
)
def resolve_alert(
    alert_id: uuid.UUID,
    payload: AlertResolveRequest,
    db: Session = Depends(get_db),
):
    """Resolve an alert with analyst debrief notes."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    alert.status = payload.status
    alert.resolution_notes = payload.resolution_notes
    alert.resolved_at = datetime.datetime.now(datetime.timezone.utc)

    db.commit()
    db.refresh(alert)
    broadcaster.publish("alert_updated", {"alert_id": str(alert.id)})
    return _to_alert_read(alert)


@router.patch(
    "/alerts/{alert_id}",
    response_model=AlertRead,
    summary="Update alert status (e.g. acknowledge, resolve, mark false positive)",
)
def update_alert(alert_id: uuid.UUID, payload: AlertUpdate, db: Session = Depends(get_db)):
    """Update lifecycle status of an operational alert."""
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")

    if payload.status:
        alert.status = payload.status
        if payload.status == "acknowledged" and not alert.acknowledged_at:
            alert.acknowledged_at = datetime.datetime.now(datetime.timezone.utc)
            if payload.acknowledged_by:
                alert.acknowledged_by = payload.acknowledged_by
        if payload.status in ("resolved", "false_positive") and not alert.resolved_at:
            alert.resolved_at = datetime.datetime.now(datetime.timezone.utc)

    if payload.severity:
        alert.severity = payload.severity
    if payload.description:
        alert.description = payload.description
    if payload.assigned_to is not None:
        alert.assigned_to = payload.assigned_to
    if payload.assigned_analyst_name is not None:
        alert.assigned_analyst_name = payload.assigned_analyst_name
    if payload.resolution_notes is not None:
        alert.resolution_notes = payload.resolution_notes
    if payload.resolved_at is not None:
        alert.resolved_at = payload.resolved_at

    db.commit()
    db.refresh(alert)
    broadcaster.publish("alert_updated", {"alert_id": str(alert.id)})
    return _to_alert_read(alert)


@router.patch(
    "/alerts/{alert_id}/status",
    response_model=AlertRead,
    summary="Update alert status directly via query parameter or body",
)
def update_alert_status(
    alert_id: uuid.UUID,
    status: str = Query(..., description="active, acknowledged, resolved, false_positive"),
    db: Session = Depends(get_db),
):
    """Directly update status of an alert."""
    return update_alert(alert_id=alert_id, payload=AlertUpdate(status=status), db=db)

