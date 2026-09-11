"""Incident Report Dossier Generation API endpoints."""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.models.facility import IndustrialFacility
from app.models.feedback import AnalystFeedback
from app.models.hotspot import Hotspot
from app.models.prediction import HotspotFeature, Prediction
from app.services.pdf_report import generate_incident_pdf
from app.services.risk import calculate_risk_score

router = APIRouter()


@router.get(
    "/reports/incident/{hotspot_id}.pdf",
    summary="Download formal incident intelligence dossier as PDF",
)
def download_incident_report(
    hotspot_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Generate and return a formal PDF dossier for the specified hotspot incident."""
    hotspot = db.scalar(select(Hotspot).where(Hotspot.id == hotspot_id))
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot incident not found")

    pred = db.scalar(select(Prediction).where(Prediction.hotspot_id == hotspot_id).order_by(Prediction.predicted_at.desc(), Prediction.id.desc()).limit(1))
    feat = db.scalar(select(HotspotFeature).where(HotspotFeature.hotspot_id == hotspot_id).order_by(HotspotFeature.computed_at.desc()).limit(1))
    alert = db.scalar(select(Alert).where(Alert.hotspot_id == hotspot_id))
    feedback = db.scalar(select(AnalystFeedback).where(AnalystFeedback.hotspot_id == hotspot_id).order_by(AnalystFeedback.created_at.desc()).limit(1))

    # Compile data dictionaries
    hotspot_dict = {
        "event_id": hotspot.event_id or f"EVT-{str(hotspot.id)[:8]}",
        "latitude": hotspot.latitude,
        "longitude": hotspot.longitude,
        "frp": hotspot.frp,
        "brightness": hotspot.brightness or hotspot.bright_ti4,
        "bright_ti4": hotspot.bright_ti4,
        "bright_ti5": hotspot.bright_ti5,
        "confidence": (hotspot.raw_data or {}).get("confidence", hotspot.confidence),
        "source": hotspot.source,
        "scan": (hotspot.raw_data or {}).get("scan"),
        "track": (hotspot.raw_data or {}).get("track"),
        "satellite": hotspot.satellite,
        "instrument": hotspot.instrument,
        "acq_date": str(hotspot.acq_date) if hotspot.acq_date else None,
        "acq_time": hotspot.acq_time,
        "daynight": hotspot.daynight or "D",
    }

    pred_dict = None
    if pred:
        pred_dict = {
            "predicted_class": pred.predicted_class,
            "confidence": pred.confidence_score,
            "stage1_prediction": pred.stage1_class,
            "uncertainty": 1.0 - pred.confidence_score if pred.confidence_score is not None else None,
            "model_version": str(pred.model_version_id) if pred.model_version_id else None,
        }
    # Proximity data
    fac_dict = None
    if feat:
        fac_dict = {
            "distance_m": feat.dist_nearest_facility * 1000 if feat.dist_nearest_facility is not None else None,
            "is_inside": feat.is_inside_facility,
            "name": "OSM infrastructure (name not linked)" if feat.dist_nearest_facility is not None else None,
        }

    # Spectral data
    spectral_dict = None
    if feat:
        spectral_dict = {
            "nbr": feat.nbr_value,
            "ndvi": feat.ndvi_value,
            "cloud_cover_percentage": feat.cloud_cover_fraction * 100 if feat.cloud_cover_fraction is not None else None,
            "land_cover_class": feat.land_cover_class,
        }

    # Reuse the stored triage assessment; exporting must not invent a new score.
    risk_dict = (feat.extra_features or {}).get("risk_assessment") if feat else None

    verification_dict = None
    if feedback:
        verification_dict = {
            "verified_class": feedback.verified_class,
            "reviewer_notes": feedback.notes,
            "verified_at": str(feedback.created_at),
        }

    # Generate PDF binary
    pdf_buffer = generate_incident_pdf(
        hotspot_data=hotspot_dict,
        prediction_data=pred_dict,
        facility_data=fac_dict,
        spectral_data=spectral_dict,
        risk_data=risk_dict,
        verification_data=verification_dict,
    )

    pdf_bytes = pdf_buffer.getvalue()
    filename = f"agninetra_incident_{str(hotspot_id)[:8]}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
