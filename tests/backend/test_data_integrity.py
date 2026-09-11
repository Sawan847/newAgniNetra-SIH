"""Regression tests for observed-data provenance, geometry, and inference safety."""
import datetime as dt
import json
import uuid
from unittest.mock import patch
import httpx
import numpy as np
import pandas as pd
import pytest
from geoalchemy2.shape import from_shape
from shapely.geometry import Point
from app.models.hotspot import Hotspot
from app.models.facility import IndustrialFacility
from app.models.prediction import Prediction
from app.services.firms import FIRMSClient
from app.services.gee import SatelliteFeatureService
from app.services.geometry import point_coordinates
from app.services.osm import OverpassClient
from ml.features.engineering import extract_full_feature_vector
from ml.models.two_stage import TwoStageThermalClassifier
from ml.training.train import load_classifier_pipeline

CSV = "latitude,longitude,bright_ti4,bright_ti5,frp,acq_date,acq_time,satellite,confidence,daynight\n22.35,69.87,330,300,0,2024-05-18,830,N,nominal,D\n"


def test_csv_original_values_and_midnight_format():
    row = FIRMSClient().parse_firms_csv(CSV)[0]
    assert row["frp"] == 0
    assert row["acq_time"] == dt.time(8, 30)
    assert row["raw_data"]["confidence"] == "nominal"
    assert row["event_id"] == FIRMSClient().parse_firms_csv(CSV)[0]["event_id"]


@pytest.mark.parametrize("content", ["", "Invalid MAP_KEY", "Error: not available", "hello,world\n1,2"])
def test_invalid_firms_response_cannot_be_successful_empty_import(content):
    with pytest.raises(ValueError):
        FIRMSClient().parse_firms_csv(content)


def test_firms_errors_do_not_leak_key(caplog):
    key = "secret-firms-map-key"
    request = httpx.Request("GET", f"https://example.org/{key}")
    response = httpx.Response(403, request=request)
    client = FIRMSClient(map_key=key, max_retries=1)
    with patch("httpx.Client.get", return_value=response), patch("app.services.firms.time.sleep"):
        with pytest.raises(RuntimeError) as error:
            client.fetch_area_csv("VIIRS_SNPP_NRT", (69, 22, 70, 23), dt.date(2024, 5, 18))
    assert key not in str(error.value)
    assert key not in caplog.text


@pytest.mark.parametrize("bbox", [[70, 23, 69, 22], [0, -91, 1, 1], [0, 0, 200, 1]])
def test_ingest_validates_bounds_before_network(client, bbox):
    response = client.post("/api/v1/ingestion/firms", json={"bbox": bbox, "start_date": "2024-01-01"})
    assert response.status_code == 422


def test_firms_api_missing_credentials(client, monkeypatch):
    monkeypatch.setattr("app.services.firms.settings.firms_map_key", "")
    monkeypatch.setattr("app.services.firms.settings.firms_api_key", "")
    response = client.post("/api/v1/ingestion/firms", json={"bbox": [69, 22, 70, 23], "start_date": "2024-01-01"})
    assert response.status_code == 503


def test_gee_unavailable_never_invents_spectral_or_landcover(monkeypatch):
    monkeypatch.setattr(SatelliteFeatureService, "_init_earth_engine", lambda self: None)
    service = SatelliteFeatureService()
    spectral = service.extract_spectral_features(22, 69, dt.date(2024, 1, 1))
    assert spectral["imagery_available"] is False
    assert spectral["ndvi_value"] is None and spectral["delta_nbr"] is None
    assert service.extract_land_cover(22, 69)["land_cover_class"] is None


def test_postgis_wkb_and_wkt_decode_same_coordinate():
    assert point_coordinates(from_shape(Point(69.87, 22.35), srid=4326)) == (22.35, 69.87)
    assert point_coordinates("SRID=4326;POINT (0 0)") == (0, 0)


def test_osm_origin_and_polygon_not_lost():
    elements = [{"type": "node", "id": 1, "lat": 0, "lon": 0, "tags": {"industrial": "refinery"}},
        {"type": "way", "id": 2, "center": {"lat": 1, "lon": 1}, "tags": {"landuse": "industrial"},
         "geometry": [{"lat": 0, "lon": 0}, {"lat": 0, "lon": 2}, {"lat": 2, "lon": 2}, {"lat": 0, "lon": 0}]}]
    facilities = OverpassClient().parse_overpass_elements({"elements": elements})
    assert facilities[0]["latitude"] == 0 and facilities[0]["longitude"] == 0
    assert "POLYGON" in facilities[1]["footprint_wkt"]


def test_prior_days_and_frp_zero_are_preserved():
    current = {"latitude": 22, "longitude": 69, "acq_date": "2024-05-18", "acq_time": "0800", "frp": 0, "satellite": "N"}
    history = [{**current, "acq_date": "2024-05-17", "frp": 10},
               {**current, "acq_date": "2024-05-17", "acq_time": "1900", "frp": 20},
               {**current, "acq_date": "2024-05-19", "frp": 999},
               {**current, "acq_date": "2024-05-18", "acq_time": "0900", "frp": 999}]
    features = extract_full_feature_vector(current, history)
    assert features["persistence_score_30d"] == 1
    assert features["nearby_hotspot_count_7d"] == 2
    assert features["historical_median_frp"] == 15
    assert features["frp_to_historical_ratio"] == 0
    assert features["land_cover_class"] is None
    assert features["ndvi_value"] is None


def test_near_facility_point_does_not_claim_polygon_containment():
    record = {"latitude": 22, "longitude": 69, "acq_date": "2024-01-01"}
    result = extract_full_feature_vector(record, facilities=[{"latitude": 22, "longitude": 69}])
    assert result["dist_nearest_facility"] == 0
    assert result["is_inside_facility"] is False


def test_csv_replay_does_not_duplicate_predictions(client, db_session, monkeypatch):
    monkeypatch.setattr("app.services.intelligence.get_classifier", lambda: None)
    first = client.post("/api/v1/ingestion/firms/csv", content=CSV, headers={"Content-Type": "text/csv"})
    assert first.status_code == 200 and first.json()["data"]["records_inserted"] == 1
    count = db_session.query(Prediction).count()
    assert count == 1
    again = client.post("/api/v1/ingestion/firms/csv", content=CSV, headers={"Content-Type": "text/csv"})
    assert again.json()["data"]["records_inserted"] == 0
    assert db_session.query(Prediction).count() == count


def test_latest_class_filter_ignores_old_predictions(client, db_session):
    h = Hotspot(id=uuid.uuid4(), latitude=22, longitude=69, geom="POINT(69 22)", acq_date=dt.date(2024, 1, 1))
    db_session.add(h)
    db_session.flush()
    for date, label in [(1, "accidental_industrial_fire"), (2, "persistent_industrial_source")]:
        db_session.add(Prediction(hotspot_id=h.id, predicted_class=label, predicted_at=dt.datetime(2024, 1, date)))
    db_session.commit()
    old = client.get("/api/v1/hotspots?fire_class=accidental_industrial_fire").json()
    assert old["meta"]["total"] == 0
    new = client.get("/api/v1/hotspots?fire_class=persistent_industrial_source").json()
    assert new["meta"]["total"] == 1
    assert new["data"][0]["predicted_class"] == "persistent_industrial_source"


def test_no_synthetic_autotraining_or_artifacts():
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as td:
        tmp_path = Path(td)
        with pytest.raises(FileNotFoundError):
            load_classifier_pipeline(str(tmp_path / "fire_classifier.joblib"))
        assert list(tmp_path.iterdir()) == []


def test_low_confidence_abstention_does_not_invent_probability_mass():
    class Stage1:
        classes_ = np.array(["industrial", "forest_or_natural_fire", "agricultural_burning", "mining_or_other"])
        def predict_proba(self, matrix): return np.tile([0.25, 0.25, 0.25, 0.25], (len(matrix), 1))
    model = TwoStageThermalClassifier(calibrate=False)
    model.stage1_model = Stage1()
    detail = model.predict_detailed(pd.DataFrame([{"frp": 0}]))[0]
    assert detail["predicted_class"] == "uncertain"
    assert detail["confidence_score"] == 0.25
    assert sum(detail["class_probabilities"].values()) == pytest.approx(1)


def test_sse_publish_from_database_worker():
    import asyncio
    from app.services.events import EventBroadcaster

    async def scenario():
        bus = EventBroadcaster()
        bus.bind(asyncio.get_running_loop())
        stream = bus.subscribe()
        assert "event: connected" in await anext(stream)
        await asyncio.to_thread(bus.publish, "hotspot_detected", {"hotspot_id": "observed-1"})
        event = await asyncio.wait_for(anext(stream), timeout=1)
        assert 'event: hotspot_detected' in event
        assert '"hotspot_id": "observed-1"' in event
        await stream.aclose()
        bus.bind(None)

    asyncio.run(scenario())


def test_report_preserves_missing_values_and_latest_prediction(client, db_session, monkeypatch):
    from io import BytesIO
    from app.models.prediction import HotspotFeature
    from app.api.v1 import reports

    h = Hotspot(id=uuid.uuid4(), event_id="report-null", latitude=22.35, longitude=69.87,
                geom="POINT(69.87 22.35)", source="FIRMS", frp=None, brightness=None,
                acq_date=dt.date(2026, 9, 10))
    db_session.add(h)
    db_session.flush()
    db_session.add_all([
        Prediction(hotspot_id=h.id, predicted_class="agricultural_burning", confidence_score=0.8,
                   predicted_at=dt.datetime(2026, 9, 9)),
        Prediction(hotspot_id=h.id, predicted_class="uncertain", confidence_score=None,
                   predicted_at=dt.datetime(2026, 9, 10)),
        HotspotFeature(hotspot_id=h.id, dist_nearest_facility=1.5, cloud_cover_fraction=None,
                       extra_features={"risk_assessment": {"risk_score": 12}}),
    ])
    db_session.commit()
    captured = {}
    def render(**kwargs):
        captured.update(kwargs)
        return BytesIO(b"%PDF-test")
    monkeypatch.setattr(reports, "generate_incident_pdf", render)
    response = client.get(f"/api/v1/reports/incident/{h.id}.pdf")
    assert response.status_code == 200
    assert captured["prediction_data"]["predicted_class"] == "uncertain"
    assert captured["prediction_data"]["confidence"] is None
    assert captured["prediction_data"]["model_version"] is None
    assert captured["facility_data"]["distance_m"] == 1500
    assert captured["spectral_data"]["cloud_cover_percentage"] is None
    assert captured["hotspot_data"]["frp"] is None
    assert captured["risk_data"]["risk_score"] == 12


def test_pdf_export_accepts_unavailable_thermal_and_model_evidence():
    from app.services.pdf_report import generate_incident_pdf
    result = generate_incident_pdf({"frp": None, "brightness": None, "latitude": 0,
                                   "longitude": 0, "event_id": "null-evidence"},
                                  prediction_data={"confidence": None})
    assert result.getvalue().startswith(b"%PDF-")
