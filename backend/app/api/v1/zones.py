"""Monitoring Zones API endpoints — User-defined surveillance perimeters."""

from __future__ import annotations

import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.zone import MonitoringZone
from app.schemas.zone import ZoneCreate, ZoneListResponse, ZoneRead

router = APIRouter()


@router.get(
    "/zones",
    response_model=ZoneListResponse,
    summary="List all user-defined surveillance zones",
)
def list_zones(
    active_only: bool = Query(False, description="Filter for active zones only"),
    db: Session = Depends(get_db),
):
    """Retrieve configured monitoring zones."""
    query = select(MonitoringZone)
    if active_only:
        query = query.where(MonitoringZone.is_active == True)

    zones = db.scalars(query.order_by(MonitoringZone.name)).all()
    return ZoneListResponse(
        status="success",
        data=[ZoneRead.model_validate(z) for z in zones],
        meta={"total": len(zones)},
    )


@router.post(
    "/zones",
    response_model=ZoneRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new geographic monitoring zone",
)
def create_zone(req: ZoneCreate, db: Session = Depends(get_db)):
    """Configure a new rectangular spatial monitoring zone."""
    if req.min_lat > req.max_lat or req.min_lon > req.max_lon:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid bounding box: min coordinates must be <= max coordinates.",
        )

    zone = MonitoringZone(
        id=uuid.uuid4(),
        name=req.name,
        description=req.description,
        min_lat=req.min_lat,
        max_lat=req.max_lat,
        min_lon=req.min_lon,
        max_lon=req.max_lon,
        sensitivity=req.sensitivity,
        alert_email=req.alert_email,
        is_active=req.is_active,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow(),
    )
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return ZoneRead.model_validate(zone)


@router.delete(
    "/zones/{zone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a monitoring zone",
)
def delete_zone(zone_id: uuid.UUID, db: Session = Depends(get_db)):
    """Remove a monitoring zone configuration."""
    zone = db.scalar(select(MonitoringZone).where(MonitoringZone.id == zone_id))
    if not zone:
        raise HTTPException(status_code=404, detail="Monitoring zone not found")

    db.delete(zone)
    db.commit()
    return None
