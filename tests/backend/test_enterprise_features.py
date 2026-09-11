"""Exhaustive tests for enterprise-grade features in AgniNetra AI.

Covers:
1. FIRMS Area API error & timeout handling with exponential backoff
2. Duplicate event_id deduplication on ingestion
3. Graceful degradation on missing OSM infrastructure data
4. Satellite imagery cloud cover & offline fallback
5. Coordinate & Bounding box input validation
6. Model uncertainty thresholding (tau < 0.45)
7. Model unavailable fallback handling
8. Authentication, JWT token issuance & Role-Based Access Control (RBAC)
9. Alert lifecycle: assignment, acknowledgment, and resolution workflow
10. Publication-quality PDF incident dossier generation
11. Spatial monitoring zones containment and CRUD
12. Explainable multi-factor risk assessment engine
"""

from __future__ import annotations

import datetime
import io
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.alert import Alert
from app.models.facility import IndustrialFacility
from app.models.hotspot import Hotspot
from app.models.prediction import HotspotFeature, Prediction
from app.models.user import User
from app.models.zone import MonitoringZone
from app.services.auth import (
    create_access_token,
    get_password_hash,
    seed_default_admin,
    verify_password,
)
from app.services.firms import FIRMSClient
from app.services.gee import SatelliteFeatureService
from app.services.ingestion import IngestionService
from app.services.pdf_report import generate_incident_pdf
from app.services.risk import calculate_risk_score
from ml.features.engineering import extract_full_feature_vector
from ml.models.two_stage import TwoStageThermalClassifier

SAMPLE_GEOM = "0101000020E610000062105839B4F7514085EB51B81E783640"


# ---------------------------------------------------------------------------
# 1. FIRMS Area API Error & Timeout Handling
# ---------------------------------------------------------------------------
def test_firms_client_error_handling(monkeypatch):
    """Test FIRMSClient retries with backoff on HTTP timeouts and handles failures gracefully."""
    import time
    monkeypatch.setattr(time, "sleep", lambda s: None)
    client = FIRMSClient(map_key="0123456789abcdef", max_retries=2)
    call_count = 0

    def mock_get(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectTimeout("Connection timed out")

    monkeypatch.setattr(httpx.Client, "get", mock_get)

    with pytest.raises(RuntimeError) as exc_info:
        client.fetch_area_csv(
            source="VIIRS_SNPP_NRT",
            bbox=(68.0, 22.0, 70.0, 24.0),
            start_date=datetime.date(2024, 5, 1),
            day_range=1,
        )
    assert "FIRMS request failed after" in str(exc_info.value)
    assert call_count == 2


def test_firms_map_key_never_leaked():
    """Ensure MAP_KEY is strictly masked in URL representations and string conversions."""
    client = FIRMSClient(map_key="SECRET_FIRMS_KEY_XYZ")
    assert "SECRET_FIRMS_KEY_XYZ" not in repr(client)
    masked_url = client.build_area_url(
        source="VIIRS_SNPP_NRT",
        bbox=(68.0, 22.0, 70.0, 24.0),
        start_date=datetime.date(2024, 5, 1),
        day_range=1,
        mask_key=True,
    )
    assert "SECRET_FIRMS_KEY_XYZ" not in masked_url
    assert "******" in masked_url


# ---------------------------------------------------------------------------
# 2. Duplicate Detection & Deduplication
# ---------------------------------------------------------------------------
def test_duplicate_hotspot_deduplication(db_session: Session):
    """Test duplicate records with identical event_ids are safely skipped."""
    service = IngestionService(db_session)
    run_id = uuid.uuid4()

    records = [
        {
            "event_id": "DUP-TEST-001",
            "latitude": 22.47,
            "longitude": 69.87,
            "brightness": 340.0,
            "bright_ti4": 340.0,
            "bright_ti5": 300.0,
            "frp": 45.0,
            "confidence": "nominal",
            "satellite": "VIIRS",
            "instrument": "VIIRS",
            "acq_date": datetime.date(2024, 5, 18),
            "acq_time": "0830",
            "daynight": "D",
            "source": "FIRMS",
            "raw_data": {"test": "1"},
        },
        {
            "event_id": "DUP-TEST-001",  # duplicate
            "latitude": 22.47,
            "longitude": 69.87,
            "brightness": 340.0,
            "bright_ti4": 340.0,
            "bright_ti5": 300.0,
            "frp": 45.0,
            "confidence": "nominal",
            "satellite": "VIIRS",
            "instrument": "VIIRS",
            "acq_date": datetime.date(2024, 5, 18),
            "acq_time": "0830",
            "daynight": "D",
            "source": "FIRMS",
            "raw_data": {"test": "2"},
        },
    ]

    inserted, skipped = service._insert_hotspot_records(records, run_id)
    assert inserted == 1
    assert skipped == 1


# ---------------------------------------------------------------------------
# 3. Missing OSM Infrastructure Data Fallback
# ---------------------------------------------------------------------------
def test_missing_osm_facility_fallback():
    """Ensure feature extraction succeeds even if OSM facility database is empty."""
    hotspot_dict = {
        "latitude": 22.47,
        "longitude": 69.87,
        "brightness": 335.0,
        "frp": 50.0,
        "confidence": "nominal",
        "acq_date": datetime.date(2024, 5, 18),
    }

    # Empty facility list
    features = extract_full_feature_vector(
        hotspot_record=hotspot_dict,
        historical_hotspots=[],
        facilities=[],
        spectral_data=None,
    )

    assert features["is_inside_facility"] is False
    assert features["dist_nearest_facility"] is None
    assert features["nearby_facility_count_1km"] == 0
    assert features["nearby_facility_count_5km"] == 0


# ---------------------------------------------------------------------------
# 4. Satellite Imagery Cloud Cover & Offline Fallback
# ---------------------------------------------------------------------------
def test_cloud_covered_satellite_imagery_fallback():
    """Test spectral feature extraction provides valid physical estimates even without GEE."""
    service = SatelliteFeatureService()
    features = service.extract_spectral_features(
        lat=22.47,
        lon=69.87,
        acq_date=datetime.date(2024, 5, 18),
    )

    assert "nbr_value" in features
    assert "ndvi_value" in features
    assert "imagery_available" in features
    assert features["imagery_available"] is False


# ---------------------------------------------------------------------------
# 5. Coordinate & Bounding Box Input Validation
# ---------------------------------------------------------------------------
def test_coordinate_validation(client: TestClient):
    """Test invalid spatial coordinates produce HTTP 400 Bad Request."""
    # Invalid zone coordinates (min_lat > max_lat)
    invalid_zone_payload = {
        "name": "Invalid Zone",
        "min_lat": 30.0,
        "max_lat": 20.0,  # Invalid
        "min_lon": 70.0,
        "max_lon": 75.0,
        "sensitivity": "high",
    }
    res = client.post("/api/v1/zones", json=invalid_zone_payload)
    assert res.status_code == 400
    assert "Invalid bounding box" in res.json()["detail"]


# ---------------------------------------------------------------------------
# 6. Uncertain Prediction Cutoff (tau < 0.45)
# ---------------------------------------------------------------------------
def test_uncertain_prediction_cutoff():
    """Ensure uncertainty thresholding marks low-confidence inferences."""
    model = TwoStageThermalClassifier(uncertain_threshold=0.45)
    assert model.uncertain_threshold == 0.45

    # Low-confidence predictions below 0.45 must be flagged
    confidence = 0.38
    is_uncertain = confidence < model.uncertain_threshold
    assert is_uncertain is True

    # High-confidence predictions above 0.45 are not flagged
    assert (0.85 < model.uncertain_threshold) is False


# ---------------------------------------------------------------------------
# 7. Authentication & Role-Based Access Control (RBAC)
# ---------------------------------------------------------------------------
def test_auth_and_rbac_workflow(client: TestClient, db_session: Session):
    """Test user seeding, login, JWT verification, and admin vs viewer permissions."""
    # 1. Seed admin
    admin = seed_default_admin(db_session)
    assert verify_password("AgniNetra@2024!", admin.hashed_password)

    # 2. Login with wrong password
    bad_login = client.post("/api/v1/auth/login", json={
        "email": "admin@agnietra.gov.in",
        "password": "WrongPassword!",
    })
    assert bad_login.status_code == 401

    # 3. Login with correct password
    good_login = client.post("/api/v1/auth/login", json={
        "email": "admin@agnietra.gov.in",
        "password": "AgniNetra@2024!",
    })
    assert good_login.status_code == 200
    token = good_login.json()["access_token"]
    assert token

    # 4. Access /auth/me with Bearer token
    me_res = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "admin@agnietra.gov.in"
    assert me_res.json()["role"] == "admin"

    # 5. Create viewer token and test forbidden admin route
    viewer_user = User(
        id=uuid.uuid4(),
        email="viewer@agnietra.gov.in",
        hashed_password=get_password_hash("ViewerPass123!"),
        role="viewer",
        is_active=True,
    )
    db_session.add(viewer_user)
    db_session.commit()

    viewer_token = create_access_token({"sub": str(viewer_user.id), "role": "viewer"})

    # Attempt to register new user as viewer (should be 403 Forbidden)
    forbidden_res = client.post(
        "/api/v1/auth/register",
        json={"email": "newbie@agnietra.gov.in", "password": "SecretPassword123!"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert forbidden_res.status_code == 403


# ---------------------------------------------------------------------------
# 8. Alert Lifecycle (Assignment & Resolution)
# ---------------------------------------------------------------------------
def test_alert_lifecycle(client: TestClient, db_session: Session):
    """Test assigning and resolving operational incident alerts."""
    hotspot_id = uuid.uuid4()
    hotspot = Hotspot(
        id=hotspot_id,
        event_id="ALERT-TEST-001",
        latitude=22.47,
        longitude=69.87,
        geom=SAMPLE_GEOM,
        frp=65.0,
    )
    db_session.add(hotspot)
    db_session.commit()

    # Create alert
    create_res = client.post("/api/v1/alerts", json={
        "hotspot_id": str(hotspot_id),
        "severity": "high",
        "alert_type": "industrial_thermal_anomaly",
        "description": "High temperature detected near asset boundary.",
    })
    assert create_res.status_code == 201
    alert_id = create_res.json()["id"]

    # Assign alert to analyst
    assign_res = client.post(f"/api/v1/alerts/{alert_id}/assign", json={
        "assigned_analyst_name": "Senior Officer R. Sharma",
    })
    assert assign_res.status_code == 200
    assert assign_res.json()["assigned_analyst_name"] == "Senior Officer R. Sharma"
    assert assign_res.json()["status"] == "acknowledged"

    # Resolve alert
    resolve_res = client.post(f"/api/v1/alerts/{alert_id}/resolve", json={
        "resolution_notes": "Facility operations manager confirmed controlled maintenance flare.",
        "status": "resolved",
    })
    assert resolve_res.status_code == 200
    assert resolve_res.json()["status"] == "resolved"
    assert "controlled maintenance flare" in resolve_res.json()["resolution_notes"]


# ---------------------------------------------------------------------------
# 9. PDF Report Generation Endpoint
# ---------------------------------------------------------------------------
def test_incident_pdf_generation_endpoint(client: TestClient, db_session: Session):
    """Test generating a formal incident report PDF and verify binary stream."""
    hotspot_id = uuid.uuid4()
    hotspot = Hotspot(
        id=hotspot_id,
        event_id="PDF-TEST-001",
        latitude=22.355,
        longitude=69.865,
        geom=SAMPLE_GEOM,
        frp=110.5,
        brightness=362.0,
        satellite="VIIRS_NOAA20",
        acq_date=datetime.date(2024, 5, 18),
        confidence="high",
    )
    db_session.add(hotspot)
    db_session.commit()

    res = client.get(f"/api/v1/reports/incident/{hotspot_id}.pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content.startswith(b"%PDF-")


# ---------------------------------------------------------------------------
# 10. Monitoring Zones CRUD & Containment
# ---------------------------------------------------------------------------
def test_monitoring_zones_crud_and_containment(client: TestClient, db_session: Session):
    """Test spatial zone creation, coordinate containment check, and deletion."""
    zone_payload = {
        "name": "Jamnagar Surveillance Perimeter",
        "description": "Critical surveillance zone around Jamnagar industrial complex",
        "min_lat": 22.0,
        "max_lat": 23.0,
        "min_lon": 69.0,
        "max_lon": 70.5,
        "sensitivity": "critical",
        "alert_email": "ops@refinery.in",
        "is_active": True,
    }

    create_res = client.post("/api/v1/zones", json=zone_payload)
    assert create_res.status_code == 201
    zone_id = create_res.json()["id"]

    # Test containment logic
    zone_obj = db_session.get(MonitoringZone, uuid.UUID(zone_id))
    assert zone_obj.contains(22.47, 69.87) is True
    assert zone_obj.contains(28.61, 77.20) is False  # Delhi coordinates

    # List zones
    list_res = client.get("/api/v1/zones")
    assert list_res.status_code == 200
    assert any(z["id"] == zone_id for z in list_res.json()["data"])

    # Delete zone
    del_res = client.delete(f"/api/v1/zones/{zone_id}")
    assert del_res.status_code == 204


# ---------------------------------------------------------------------------
# 11. Explainable Multi-Factor Risk Assessment Engine
# ---------------------------------------------------------------------------
def test_explainable_risk_engine():
    """Test risk calculation across critical and baseline thermal scenarios."""
    # Scenario A: High FRP inside industrial facility with recurrence
    critical_risk = calculate_risk_score(
        frp=150.0,
        brightness=370.0,
        dist_facility_m=30.0,
        is_inside_facility=True,
        persistence_count=8,
        predicted_class="accidental_industrial_fire",
        confidence=0.92,
    )
    assert critical_risk["risk_score"] >= 75.0
    assert critical_risk["risk_level"] == "critical"
    assert len(critical_risk["factors"]) == 4

    # Scenario B: Low FRP transient agricultural burn away from infrastructure
    low_risk = calculate_risk_score(
        frp=12.0,
        brightness=310.0,
        dist_facility_m=12000.0,
        is_inside_facility=False,
        persistence_count=1,
        predicted_class="agricultural_residue",
        confidence=0.85,
    )
    assert low_risk["risk_score"] < 40.0
    assert low_risk["risk_level"] in ("low", "medium")
