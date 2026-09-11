"""Predictions and ML Inference API endpoints."""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.alert import Alert
from app.models.facility import IndustrialFacility
from app.models.hotspot import Hotspot
from app.models.prediction import HotspotFeature, Prediction
from app.schemas.prediction import (
    PredictionListResponse,
    PredictionRead,
    PredictResponse,
)
from app.services.gee import SatelliteFeatureService

router = APIRouter()

satellite_service = SatelliteFeatureService()

# This module no longer loads a classifier of its own. /predict delegates to
# app.services.intelligence.run_intelligence_pipeline, which is the single place
# inference happens - so there is one feature path and one model, and the two cannot
# drift apart.
#
# The removed loader called ml.training.train.load_classifier_pipeline, which trained
# on synthetically generated per-class feature distributions when no artifact was
# found. That meant a production endpoint could fit a model to invented data on its
# first request and then serve it indefinitely.


@router.get(
    "/predictions",
    response_model=PredictionListResponse,
    summary="Query historical model predictions",
)
def list_predictions(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    predicted_class: Optional[str] = Query(None, description="Filter by class"),
    hotspot_id: Optional[uuid.UUID] = Query(None),
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0),
    db: Session = Depends(get_db),
):
    """Retrieve paginated model prediction logs."""
    query = db.query(Prediction)
    if hotspot_id:
        query = query.filter(Prediction.hotspot_id == hotspot_id)
    if predicted_class:
        query = query.filter(Prediction.predicted_class == predicted_class)
    if min_confidence is not None:
        query = query.filter(Prediction.confidence_score >= min_confidence)

    total = query.count()
    rows = query.order_by(desc(Prediction.predicted_at)).offset((page - 1) * per_page).limit(per_page).all()

    return PredictionListResponse(
        status="success",
        data=[PredictionRead.model_validate(r) for r in rows],
        meta={"total": total, "page": page, "per_page": per_page},
    )


@router.post(
    "/predict/{hotspot_id}",
    response_model=PredictResponse,
    summary="Execute end-to-end feature extraction, two-stage classification, and alert triggers",
)
def run_prediction_for_hotspot(hotspot_id: uuid.UUID, db: Session = Depends(get_db)):
    """Run full intelligence pipeline for a specific hotspot record."""
    from app.services.intelligence import run_intelligence_pipeline

    hotspot = db.query(Hotspot).filter(Hotspot.id == hotspot_id).first()
    if not hotspot:
        raise HTTPException(status_code=404, detail="Hotspot not found")

    result = run_intelligence_pipeline(db, hotspot_id)
    pred_obj = result["prediction"]
    alert_obj = result.get("alert")

    return PredictResponse(
        status="success",
        data=PredictionRead.model_validate(pred_obj),
        alert_created=alert_obj is not None,
        alert_id=alert_obj.id if alert_obj else None,
    )
