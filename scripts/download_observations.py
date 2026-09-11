"""Download a dated, reproducible NASA FIRMS / OSM demonstration snapshot.

Run from the repository root. No API key is needed for NASA public NRT CSVs.
This does not label thermal anomalies as verified industrial accidents.
"""
import csv
import datetime as dt
import hashlib
import io
import json
import sys
import uuid
from pathlib import Path
import httpx
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.services.firms import FIRMSClient
from app.services.osm import OverpassClient


def main():
    raw = ROOT / "data" / "raw" / "observed"
    public = ROOT / "frontend" / "public" / "data"
    raw.mkdir(parents=True, exist_ok=True)
    public.mkdir(parents=True, exist_ok=True)
    url = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/viirs/csv/SUOMI_VIIRS_C2_South_Asia_7d.csv"
    response = httpx.get(url, timeout=60, follow_redirects=True)
    response.raise_for_status()
    records = FIRMSClient().parse_firms_csv(response.text, "NASA_FIRMS_PUBLIC_SNAPSHOT")
    records = [r for r in records if 68 <= r["longitude"] <= 98 and 6 <= r["latitude"] <= 38]
    if not records:
        raise RuntimeError("NASA response contains no observations in the selected India bounding box")
    (raw / "firms_south_asia_7d.csv").write_text(response.text, encoding="utf-8")
    fetched = dt.datetime.now(dt.timezone.utc).isoformat()
    hotspots = []
    for record in records:
        h = {k: v for k, v in record.items() if k != "raw_data"}
        h.update(id=str(uuid.uuid5(uuid.NAMESPACE_URL, record["event_id"])), ingested_at=fetched,
                 predicted_class=None, confidence_score=None)
        hotspots.append(h)
    facilities = []
    osm_status = "unavailable"
    try:
        osm = OverpassClient(endpoint_url="https://overpass-api.de/api/interpreter", max_retries=1).fetch_infrastructure((69.80, 22.30, 69.95, 22.40))
        (raw / "osm_jamnagar.json").write_text(json.dumps(osm, indent=2), encoding="utf-8")
        facilities = [{"id": str(uuid.uuid5(uuid.NAMESPACE_URL, r["osm_id"])),
            "name": r["name"] or r["facility_type"], "facility_type": r["facility_type"],
            "osm_id": r["osm_id"], "latitude": r["latitude"], "longitude": r["longitude"],
            "source": "OSM_OVERPASS", "created_at": fetched, "metadata": r["metadata"]} for r in osm]
        osm_status = "downloaded"
    except Exception as exc:
        print(f"OSM snapshot unavailable: {type(exc).__name__}")
    manifest = {"fetched_at": fetched, "firms_url": url,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "source": "NASA FIRMS Suomi-NPP VIIRS NRT; public rolling 7-day download",
        "min_acquisition_date": str(min(r["acq_date"] for r in records)),
        "max_acquisition_date": str(max(r["acq_date"] for r in records)),
        "hotspot_count": len(hotspots), "facility_count": len(facilities), "osm_status": osm_status,
        "label_status": "Unlabelled observations; no verified incident classes",
        "attribution": "NASA FIRMS / LANCE; OpenStreetMap contributors (ODbL)"}
    (public / "observations.json").write_text(json.dumps({"manifest": manifest,
        "hotspots": hotspots, "facilities": facilities}, default=str), encoding="utf-8")
    (raw / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))

if __name__ == "__main__":
    main()
