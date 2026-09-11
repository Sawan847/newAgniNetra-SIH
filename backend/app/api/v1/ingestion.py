"""Ingestion endpoints — trigger and monitor FIRMS data ingestion runs."""

from __future__ import annotations

import logging
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.ingestion import IngestionRun
from app.schemas.ingestion import FIRMSIngestRequest, FIRMSIngestResponse, IngestionRunRead, OSMIngestRequest
from app.services.ingestion import IngestionService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/ingestion/firms", response_model=FIRMSIngestResponse, status_code=202)
def trigger_firms_ingestion(
    body: FIRMSIngestRequest,
    db: Session = Depends(get_db),
) -> FIRMSIngestResponse:
    """Trigger a FIRMS data ingestion run for the specified bounding box and date range.

    The MAP_KEY is never logged, returned, or exposed in any response.
    """
    service = IngestionService(db)
    if not service.firms_client.is_configured():
        raise HTTPException(status_code=503, detail="Set FIRMS_MAP_KEY in the project .env or import a NASA FIRMS CSV")

    try:
        run = service.run_firms_ingestion(
            bbox=body.bbox,
            start_date=body.start_date,
            end_date=body.end_date,
            sources=body.sources,
        )
    except Exception as exc:
        logger.error("FIRMS ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Ingestion failed; check the server ingestion log")

    status_msg = (
        f"Ingestion {run.status}: {run.records_inserted} inserted, "
        f"{run.records_skipped} skipped out of {run.records_fetched} fetched."
    )

    return FIRMSIngestResponse(
        status=run.status,
        message=status_msg,
        run_id=run.id,
        data=IngestionRunRead.model_validate(run),
    )


@router.get("/ingestion/runs", response_model=List[IngestionRunRead])
def list_ingestion_runs(
    status: Optional[str] = Query(None, description="Filter by status: running, completed, failed"),
    limit: int = Query(20, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[IngestionRunRead]:
    """List recent ingestion runs with optional status filter."""
    query = db.query(IngestionRun)

    if status:
        query = query.filter(IngestionRun.status == status)

    runs = query.order_by(IngestionRun.started_at.desc()).offset(offset).limit(limit).all()
    return [IngestionRunRead.model_validate(r) for r in runs]


@router.post("/ingestion/osm")
def import_osm(body: OSMIngestRequest, db: Session = Depends(get_db)):
    """Import real OSM facilities, preserve tags and simple polygon footprints."""
    from app.services.osm import OverpassClient
    from app.models.facility import IndustrialFacility
    try:
        facilities = OverpassClient().fetch_infrastructure(body.bbox)
        inserted, updated = 0, 0
        for record in facilities:
            facility = db.query(IndustrialFacility).filter_by(osm_id=record["osm_id"]).first()
            if facility is None:
                facility = IndustrialFacility(osm_id=record["osm_id"])
                db.add(facility)
                inserted += 1
            else:
                updated += 1
            facility.name = record["name"]
            facility.facility_type = record["facility_type"]
            facility.location = record["location_wkt"]
            facility.footprint = record.get("footprint_wkt")
            facility.source = record["source"]
            facility.metadata_ = record["metadata"]
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=502, detail="OSM import failed. Try a smaller region or retry later.") from None
    return {"status": "completed", "inserted": inserted, "updated": updated, "source": "OSM_OVERPASS"}


@router.post("/ingestion/firms/csv", response_model=FIRMSIngestResponse)
def import_firms_csv(content: str = Body(..., media_type="text/csv", max_length=10_000_000), db: Session = Depends(get_db)):
    """Import a downloaded FIRMS VIIRS CSV, retaining original records and lineage."""
    import datetime
    import hashlib
    from app.models.ingestion import AuditLog
    service = IngestionService(db)
    try:
        records = service.firms_client.parse_firms_csv(content, "FIRMS_CSV_IMPORT")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    run = IngestionRun(id=uuid.uuid4(), source="FIRMS_CSV_IMPORT", status="running",
                       records_fetched=len(records), records_inserted=0, records_skipped=0)
    db.add(run)
    db.commit()
    try:
        inserted, skipped = service._insert_hotspot_records(records, run.id)
        run.records_inserted, run.records_skipped = inserted, skipped
        run.status = "completed"
        db.add(AuditLog(action="firms_csv_import", resource_type="ingestion_runs", resource_id=run.id,
                       details={"sha256": hashlib.sha256(content.encode()).hexdigest(), "rows": len(records)}))
    except Exception:
        db.rollback()
        run.status = "failed"
        run.error_message = "CSV persistence failed; review server logs and retry"
    run.completed_at = datetime.datetime.now(datetime.timezone.utc)
    db.commit()
    db.refresh(run)
    return FIRMSIngestResponse(status=run.status, message=f"CSV import {run.status}", run_id=run.id,
                               data=IngestionRunRead.model_validate(run))
