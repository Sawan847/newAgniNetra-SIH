"""Industrial Facilities API endpoints with spatial filtering and GeoJSON export."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.services.geometry import point_coordinates, validate_bbox

from app.database import get_db
from app.models.facility import IndustrialFacility
from app.schemas.facility import (
    FacilityGeoJSONFeature,
    FacilityGeoJSONFeatureCollection,
    FacilityListResponse,
    FacilityRead,
)

router = APIRouter()


@router.get(
    "/facilities",
    response_model=None,
    summary="Query industrial infrastructure, refineries, and power plants",
)
def list_facilities(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=500, description="Items per page"),
    facility_type: Optional[str] = Query(None, description="Filter by type (refinery, power_plant, industrial, mining)"),
    search: Optional[str] = Query(None, description="Search facility name or operator"),
    bbox: Optional[str] = Query(None, description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    format: str = Query("json", description="Output format: 'json' or 'geojson'"),
    db: Session = Depends(get_db),
):
    """Retrieve industrial facilities with search and GeoJSON format support."""
    query = db.query(IndustrialFacility)

    if facility_type:
        query = query.filter(IndustrialFacility.facility_type.ilike(f"%{facility_type}%"))
    if search:
        query = query.filter(IndustrialFacility.name.ilike(f"%{search}%"))

    if bbox:
        try:
            west, south, east, north = validate_bbox(tuple(float(x) for x in bbox.split(",")))
        except (ValueError, TypeError):
            raise HTTPException(400, "Invalid bounding box") from None
        query = query.filter(func.ST_Intersects(IndustrialFacility.location, func.ST_MakeEnvelope(west, south, east, north, 4326)))
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    items = []
    for r in rows:
        lat, lon = point_coordinates(r.location)

        items.append({
            "id": r.id,
            "name": r.name,
            "facility_type": r.facility_type,
            "osm_id": r.osm_id,
            "source": r.source,
            "latitude": lat,
            "longitude": lon,
            "metadata": r.metadata_,
            "created_at": r.created_at,
        })

    if format.lower() == "geojson":
        features = [
            FacilityGeoJSONFeature(
                id=str(item["id"]),
                geometry={
                    "type": "Point",
                    "coordinates": [item["longitude"], item["latitude"]],
                },
                properties={k: v for k, v in item.items() if k not in ("latitude", "longitude")},
            )
            for item in items if item["latitude"] is not None and item["longitude"] is not None
        ]
        return FacilityGeoJSONFeatureCollection(
            features=features,
            meta={"total": total, "page": page, "per_page": per_page},
        )

    return FacilityListResponse(
        status="success",
        data=[FacilityRead.model_validate(item) for item in items],
        meta={"total": total, "page": page, "per_page": per_page},
    )


@router.get(
    "/facilities/{facility_id}",
    response_model=FacilityRead,
    summary="Get single facility by UUID",
)
def get_facility(facility_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve details for a specific industrial facility."""
    r = db.query(IndustrialFacility).filter(IndustrialFacility.id == facility_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Facility not found")

    lat, lon = point_coordinates(r.location)

    return FacilityRead(
        id=r.id,
        name=r.name,
        facility_type=r.facility_type,
        osm_id=r.osm_id,
        source=r.source,
        latitude=lat,
        longitude=lon,
        metadata=r.metadata_,
        created_at=r.created_at,
    )
