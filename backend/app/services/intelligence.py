"""AgniNetra AI — Comprehensive Intelligence & Prediction Pipeline.

Enriches hotspots with GIS and Sentinel-2 features, executes two-stage ML inference,
calculates explainable multi-factor risk scores, enforces monitoring zones, and raises alerts.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

import pandas as pd
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.alert import Alert
from app.models.facility import IndustrialFacility
from app.models.hotspot import Hotspot
from app.models.prediction import HotspotFeature, Prediction
from app.models.zone import MonitoringZone
from app.services.email import send_alert_email
from app.services.events import broadcaster
from app.services.gee import SatelliteFeatureService
from app.services.risk import calculate_risk_score
from app.services.geometry import point_coordinates, decode_geometry
from ml.features.engineering import extract_full_feature_vector
from app.services.classifier import classifier_service

logger = logging.getLogger(__name__)

# Global singletons
satellite_service = SatelliteFeatureService()

def _landcover_to_code(landcover) -> int:
    """Map a land-cover label onto the ESA WorldCover codes the labelling rules use.

    ml.labeling.weak_labels reads numeric WorldCover codes (10 tree, 20 shrub,
    40 cropland, 50 built-up, 60 bare). This service carries land cover as a string,
    so without translation every detection would arrive with an unknown surface type
    and the wildfire and crop-residue rules could not fire.

    Returns 0 for anything unrecognised, which the rules treat as "unknown" and
    handle with their behavioural fallbacks - never as a guess.
    """
    t = str(landcover or "").strip().lower()
    if not t:
        return 0
    if any(k in t for k in ("forest", "tree", "wood")):
        return 10
    if any(k in t for k in ("shrub", "scrub")):
        return 20
    if any(k in t for k in ("grass", "meadow", "herbaceous")):
        return 30
    if any(k in t for k in ("crop", "farm", "agri", "orchard")):
        return 40
    if any(k in t for k in ("built", "urban", "industrial", "settlement")):
        return 50
    if any(k in t for k in ("bare", "sparse", "quarry", "mine", "rock", "sand")):
        return 60
    return 0


def get_classifier():
    """Return the site-level classifier service, or None if no artifact is present.

    Previously loaded fire_classifier.joblib through
    ml.training.train.load_classifier_pipeline - the deprecated two-stage model fitted
    on synthetically generated per-class feature distributions. That model learned to
    invert the generator's if-statements, so every prediction it served carried no
    information about real fires. It now loads the artifact produced by
    ml.training.train_pipeline from weakly-supervised real detections.
    """
    return classifier_service if classifier_service.load() else None


def run_intelligence_pipeline(
    db: Session,
    hotspot_id: uuid.UUID,
) -> dict[str, Any]:
    """Execute complete intelligence enrichment, prediction, risk scoring, and alerting."""
    hotspot = db.query(Hotspot).filter(Hotspot.id == hotspot_id).first()
    if not hotspot:
        raise ValueError(f"Hotspot {hotspot_id} not found")

    # 1. Nearby facilities for spatial proximity
    db_facilities = db.query(IndustrialFacility).all()
    facility_dicts = []
    for f in db_facilities:
        if str(f.source or "").upper().startswith("DEMO"):
            continue
        f_lat, f_lon = point_coordinates(f.location)
        if f_lat is None or f_lon is None:
            continue
        footprint = decode_geometry(f.footprint)
        facility_dicts.append({
            "id": f.id,
            "name": f.name,
            "facility_type": f.facility_type,
            "latitude": f_lat,
            "longitude": f_lon,
            "footprint_wkt": footprint.wkt if footprint is not None else None,
        })

    # 2. Historical hotspots for persistence baselines
    hist_records = (
        db.query(Hotspot)
        .filter(Hotspot.id != hotspot.id)
        .filter(Hotspot.latitude.between(hotspot.latitude - 0.2, hotspot.latitude + 0.2))
        .filter(Hotspot.longitude.between(hotspot.longitude - 0.2, hotspot.longitude + 0.2))
        .filter(Hotspot.acq_date >= hotspot.acq_date - datetime.timedelta(days=90))
        .filter(Hotspot.acq_date <= hotspot.acq_date)
        .filter(~Hotspot.source.like("DEMO%"))
        .all()
    )
    hist_dicts = [
        {"latitude": h.latitude, "longitude": h.longitude, "acq_date": h.acq_date, "acq_time": h.acq_time, "satellite": h.satellite, "frp": h.frp}
        for h in hist_records
    ]

    # 3. Sentinel-2 spectral indices
    spectral = satellite_service.extract_spectral_features(
        lat=hotspot.latitude,
        lon=hotspot.longitude,
        acq_date=hotspot.acq_date or datetime.date.today(),
    )

    land_cover = satellite_service.extract_land_cover(hotspot.latitude, hotspot.longitude)

    # 4. Feature vector extraction
    hotspot_dict = {
        "latitude": hotspot.latitude,
        "longitude": hotspot.longitude,
        "brightness": hotspot.brightness,
        "bright_ti4": hotspot.bright_ti4,
        "bright_ti5": hotspot.bright_ti5,
        "frp": hotspot.frp,
        "confidence": hotspot.confidence,
        "satellite": hotspot.satellite,
        "acq_date": hotspot.acq_date,
        "acq_time": hotspot.acq_time,
        "land_cover_class": land_cover["land_cover_class"],
        "daynight": hotspot.daynight,
    }
    feature_dict = extract_full_feature_vector(
        hotspot_record=hotspot_dict,
        historical_hotspots=hist_dicts,
        facilities=facility_dicts,
        spectral_data=spectral,
    )

    # 5. Save or update HotspotFeature
    existing_feat = db.query(HotspotFeature).filter(HotspotFeature.hotspot_id == hotspot.id).first()
    if existing_feat:
        for k, v in feature_dict.items():
            if hasattr(existing_feat, k):
                setattr(existing_feat, k, v)
        feat_obj = existing_feat
    else:
        feat_obj = HotspotFeature(
            id=uuid.uuid4(),
            hotspot_id=hotspot.id,
            dist_nearest_facility=feature_dict.get("dist_nearest_facility"),
            is_inside_facility=bool(feature_dict.get("is_inside_facility")),
            nearby_facility_count_1km=int(feature_dict.get("nearby_facility_count_1km", 0)),
            nearby_facility_count_5km=int(feature_dict.get("nearby_facility_count_5km", 0)),
            dist_nearest_forest=feature_dict.get("dist_nearest_forest"),
            dist_nearest_cropland=feature_dict.get("dist_nearest_cropland"),
            dist_nearest_mine=feature_dict.get("dist_nearest_mine"),
            dist_nearest_settlement=feature_dict.get("dist_nearest_settlement"),
            nearby_hotspot_count_24h=int(feature_dict.get("nearby_hotspot_count_24h", 0)),
            nearby_hotspot_count_7d=int(feature_dict.get("nearby_hotspot_count_7d", 0)),
            nearby_hotspot_count_30d=int(feature_dict.get("nearby_hotspot_count_30d", 0)),
            nearby_hotspot_count_90d=int(feature_dict.get("nearby_hotspot_count_90d", 0)),
            persistence_score=feature_dict.get("persistence_score"),
            persistence_score_30d=feature_dict.get("persistence_score_30d"),
            recurrence_rate=feature_dict.get("recurrence_rate"),
            historical_median_frp=feature_dict.get("historical_median_frp"),
            historical_max_frp=feature_dict.get("historical_max_frp"),
            frp_to_historical_ratio=feature_dict.get("frp_to_historical_ratio"),
            cluster_size=feature_dict.get("cluster_size"),
            cluster_spread_km=feature_dict.get("cluster_spread_km"),
            cluster_direction_deg=feature_dict.get("cluster_direction_deg"),
            spatial_density_5km=feature_dict.get("spatial_density_5km"),
            land_cover_class=feature_dict.get("land_cover_class"),
            ndvi_value=feature_dict.get("ndvi_value"),
            nbr_value=feature_dict.get("nbr_value"),
            ndmi_value=feature_dict.get("ndmi_value"),
            delta_nbr=feature_dict.get("delta_nbr"),
            cloud_cover_fraction=feature_dict.get("cloud_cover_fraction"),
            imagery_available=bool(feature_dict.get("imagery_available")),
            is_nighttime=bool(feature_dict.get("is_nighttime")),
            day_of_year=int(feature_dict.get("day_of_year", 1)),
        )
        db.add(feat_obj)

    # 6. ML Model Inference
    #
    # The neighbourhood is passed in deliberately: persistence ratio and a site's own
    # FRP baseline - the two features that separate a routine gas flare from an
    # industrial accident - cannot be computed from a single detection.
    model = get_classifier()
    if model is not None:
        pred_details = model.classify_hotspot_legacy(
            hotspot_record={
                "latitude": hotspot.latitude,
                "longitude": hotspot.longitude,
                "bright_ti4": hotspot.bright_ti4 if hotspot.bright_ti4 is not None else hotspot.brightness,
                "bright_ti5": hotspot.bright_ti5,
                "frp": hotspot.frp,
                "confidence": hotspot.confidence,
                "acq_date": hotspot.acq_date.isoformat() if hotspot.acq_date else None,
                "daynight": hotspot.daynight or "D",
                "satellite": hotspot.satellite,
                "land_cover_class": _landcover_to_code(land_cover),
            },
            neighbour_records=[
                {
                    "latitude": h["latitude"],
                    "longitude": h["longitude"],
                    "bright_ti4": None,
                    "bright_ti5": None,
                    "frp": h.get("frp"),
                    "confidence": None,
                    "acq_date": h["acq_date"].isoformat() if h.get("acq_date") else None,
                    "daynight": "D",
                    "satellite": h.get("satellite"),
                    "land_cover_class": 0,
                }
                for h in hist_dicts
                if h.get("acq_date") is not None
            ],
            facilities=facility_dicts,
        )
    else:
        pred_details = {
            "predicted_class": "uncertain", "confidence_score": None,
            "class_probabilities": None, "feature_importances": {},
            "explanation": {"primary_driver": "No validated model is installed",
                            "top_factors": ["Import observed data and train on independently verified labels before claiming classification accuracy."],
                            "method": "abstention"},
        }
    provenance = {"thermal_source": hotspot.source, "spectral_source": spectral.get("data_source"),
                  "land_cover": land_cover, "facility_source": "OSM / imported facilities",
                  "facility_count": len(facility_dicts), "distance_unit": "km",
                  "historical_radius_km": 1, "persistence_unit": "distinct prior acquisition days",
                  "missing_features": [k for k, v in feature_dict.items() if v is None]}
    feat_obj.extra_features = provenance
    pred_details.setdefault("explanation", {})["data_provenance"] = provenance

    # 7. Multi-Factor Risk Assessment
    dist_facility = feature_dict.get("dist_nearest_facility")
    is_in_fac = bool(feature_dict.get("is_inside_facility"))
    persistence_30d = int(feature_dict.get("persistence_score_30d", 0))

    risk_result = calculate_risk_score(
        frp=hotspot.frp,
        brightness=hotspot.brightness or hotspot.bright_ti4,
        dist_facility_m=dist_facility * 1000 if dist_facility is not None else None,
        is_inside_facility=is_in_fac,
        persistence_count=persistence_30d,
        predicted_class=pred_details["predicted_class"],
        confidence=pred_details.get("confidence_score") or 0.0,
    )

    feat_obj.extra_features = {**provenance, "risk_assessment": risk_result}

    # 8. Save/Update Prediction Record
    pred_obj = Prediction(
        id=uuid.uuid4(),
        hotspot_id=hotspot.id,
        predicted_class=pred_details["predicted_class"],
        confidence_score=pred_details["confidence_score"],
        stage1_class=pred_details.get("stage1_class"),
        stage2_class=pred_details.get("stage2_class"),
        class_probabilities=pred_details.get("class_probabilities"),
        feature_importances=pred_details.get("feature_importances"),
        explanation=pred_details.get("explanation"),
        predicted_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db.add(pred_obj)
    db.flush()

    # 9. Check User-Defined Monitoring Zones
    active_zones = db.query(MonitoringZone).filter(MonitoringZone.is_active == True).all()
    triggered_zones: list[MonitoringZone] = []
    for zone in active_zones:
        if zone.contains(hotspot.latitude, hotspot.longitude):
            triggered_zones.append(zone)

    # 10. Alert Creation Logic
    alert_created = False
    alert_obj = None
    severity = risk_result["risk_level"]

    # If inside a critical zone, elevate severity
    if any(z.sensitivity == "critical" for z in triggered_zones):
        severity = "critical"

    should_alert = (
        severity in ("critical", "high")
        or pred_details["predicted_class"] == "accidental_industrial_fire"
        or len(triggered_zones) > 0
    ) and pred_details["predicted_class"] != "uncertain" and not str(hotspot.source or "").upper().startswith("DEMO")

    if should_alert:
        # Check existing alert
        existing_alert = db.query(Alert).filter(Alert.hotspot_id == hotspot.id).first()
        if not existing_alert:
            zone_names = ", ".join(z.name for z in triggered_zones) if triggered_zones else "None"
            desc = (
                f"[{severity.upper()}] Risk {risk_result['risk_score']}/100: "
                f"{pred_details['predicted_class'].replace('_', ' ').title()} detected at "
                f"({hotspot.latitude:.4f}, {hotspot.longitude:.4f}). FRP: {hotspot.frp} MW. "
                f"Zone: {zone_names}."
            )
            alert_obj = Alert(
                id=uuid.uuid4(),
                hotspot_id=hotspot.id,
                prediction_id=pred_obj.id,
                severity=severity,
                alert_type=pred_details["predicted_class"],
                status="active",
                risk_score=risk_result["risk_score"],
                description=desc,
                metadata_={
                    "risk_details": risk_result,
                    "triggered_zones": [z.name for z in triggered_zones],
                },
            )
            db.add(alert_obj)
            db.flush()
            alert_created = True

            # Send optional notification email
            email_recipients = [z.alert_email for z in triggered_zones if z.alert_email]
            for recip in email_recipients:
                send_alert_email(
                    recipient=recip,
                    subject=f"Thermal Alert: {pred_details['predicted_class']} ({severity.upper()})",
                    alert_payload={
                        "hotspot_id": str(hotspot.id),
                        "severity": severity,
                        "risk_score": risk_result["risk_score"],
                        "predicted_class": pred_details["predicted_class"],
                        "latitude": hotspot.latitude,
                        "longitude": hotspot.longitude,
                        "frp": hotspot.frp,
                    },
                )

    db.commit()
    db.refresh(pred_obj)
    if alert_obj:
        db.refresh(alert_obj)

    # 11. Broadcast SSE telemetry to connected frontend clients
    telemetry_payload = {
        "hotspot_id": str(hotspot.id),
        "latitude": hotspot.latitude,
        "longitude": hotspot.longitude,
        "frp": hotspot.frp,
        "predicted_class": pred_obj.predicted_class,
        "confidence": pred_obj.confidence_score,
        "risk_score": risk_result["risk_score"],
        "risk_level": risk_result["risk_level"],
        "alert_id": str(alert_obj.id) if alert_obj else None,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    broadcaster.publish("hotspot_detected", telemetry_payload)
    if alert_created:
        broadcaster.publish("alert_raised", telemetry_payload)

    return {
        "hotspot": hotspot,
        "feature": feat_obj,
        "prediction": pred_obj,
        "risk": risk_result,
        "alert": alert_obj,
        "triggered_zones": triggered_zones,
    }
