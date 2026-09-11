"""AgniNetra AI — OpenStreetMap Overpass Integration Service.

Queries the Overpass API for industrial infrastructure, refineries, power plants,
quarries/mines, and settlements with rate-limit respect and caching.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class OverpassClient:
    """Client for retrieving geospatial infrastructure from OpenStreetMap via Overpass API."""

    def __init__(
        self,
        endpoint_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.endpoint_url = (endpoint_url or settings.osm_overpass_url).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def build_industrial_query(self, bbox: Tuple[float, float, float, float]) -> str:
        """Construct an Overpass QL query for thermal/industrial infrastructure within a bbox.

        BBox format for Overpass: (min_lat, min_lon, max_lat, max_lon)
        """
        min_lon, min_lat, max_lon, max_lat = bbox
        bbox_str = f"{min_lat},{min_lon},{max_lat},{max_lon}"

        from app.services.geometry import validate_bbox
        validate_bbox(bbox)
        query = f"""
        [out:json][timeout:60];
        (
          nwr["landuse"="industrial"]({bbox_str});
          nwr["power"="plant"]({bbox_str});
          nwr["man_made"~"^(works|petroleum_refinery|flare)$"]({bbox_str});
          nwr["industrial"]({bbox_str});
          nwr["landuse"~"^(quarry|surface_mining)$"]({bbox_str});
        );
        out center geom;
        """
        return query.strip()

    def fetch_infrastructure(
        self, bbox: Tuple[float, float, float, float]
    ) -> List[Dict[str, Any]]:
        """Query Overpass API for infrastructure elements within bounding box."""
        query = self.build_industrial_query(bbox)
        min_lon, min_lat, max_lon, max_lat = bbox
        bbox_key = f"{min_lon}_{min_lat}_{max_lon}_{max_lat}"

        cached = self._load_cached_response(bbox_key)
        if cached is not None:
            logger.info("Loaded OSM infrastructure from cache for bbox: %s", bbox)
            return self.parse_overpass_elements(cached)

        headers = {
            "User-Agent": "AgniNetra-SIH26162/0.2.0",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Querying Overpass API (attempt %d/%d)...", attempt, self.max_retries)
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(
                        self.endpoint_url,
                        data={"data": query},
                        headers=headers,
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("remark") or "elements" not in data:
                        raise ValueError("Incomplete Overpass response")
                    self._cache_raw_response(bbox_key, data)
                    return self.parse_overpass_elements(data)
                elif resp.status_code == 429 or resp.status_code == 504:
                    wait_sec = 30
                    logger.warning("Overpass rate limited / busy (HTTP %d). Waiting %ds...", resp.status_code, wait_sec)
                    time.sleep(wait_sec)
                else:
                    logger.error("Overpass API returned HTTP %d", resp.status_code)
                    resp.raise_for_status()
            except Exception as exc:
                last_exc = exc
                wait_sec = attempt * 3
                logger.warning("Overpass attempt %d failed: %s. Backing off %ds...", attempt, exc, wait_sec)
                time.sleep(wait_sec)

        logger.error("Overpass query failed after %d retries: %s", self.max_retries, last_exc)
        raise RuntimeError("OSM Overpass request failed; retry later") from None

    def parse_overpass_elements(self, raw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Parse Overpass JSON elements into standardized facility records."""
        elements = raw_data.get("elements", [])
        facilities = []

        for elem in elements:
            tags = elem.get("tags", {})
            if not tags:
                continue

            elem_id = f"osm_{elem.get('type', 'node')}_{elem.get('id')}"
            name = tags.get("name") or tags.get("operator") or tags.get("description")

            # Determine facility type
            facility_type = "industrial"
            if "power" in tags and tags["power"] == "plant":
                facility_type = "power_plant"
            elif "industrial" in tags:
                facility_type = f"industrial_{tags['industrial']}"
            elif tags.get("landuse") in ("quarry", "surface_mining"):
                facility_type = "mining"
            elif "refinery" in tags or tags.get("man_made") == "petroleum_refinery":
                facility_type = "refinery"

            # Coordinate extraction
            lat = elem.get("lat", elem.get("center", {}).get("lat"))
            lon = elem.get("lon", elem.get("center", {}).get("lon"))

            if lat is None or lon is None:
                continue

            record = {
                "osm_id": elem_id,
                "name": name,
                "facility_type": facility_type,
                "latitude": float(lat),
                "longitude": float(lon),
                "location_wkt": f"POINT({lon} {lat})",
                "source": "OSM_OVERPASS",
                "metadata": tags,
            }
            # Only a closed way is a trustworthy simple footprint. Complex relations
            # remain points until their multipolygon topology is assembled.
            geometry = elem.get("geometry", [])
            if elem.get("type") == "way" and len(geometry) >= 4 and geometry[0] == geometry[-1]:
                from shapely.geometry import Polygon
                polygon = Polygon([(p["lon"], p["lat"]) for p in geometry])
                if polygon.is_valid and not polygon.is_empty:
                    record["footprint_wkt"] = polygon.wkt
            facilities.append(record)

        return facilities

    def _cache_raw_response(self, bbox_key: str, data: Dict[str, Any]) -> Path:
        """Save Overpass JSON response to data/raw/osm for caching."""
        cache_dir = settings.get_raw_dir("osm")
        bbox_hash = hashlib.md5(bbox_key.encode("utf-8")).hexdigest()[:10]
        file_path = cache_dir / f"overpass_{bbox_hash}.json"
        file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return file_path

    def _load_cached_response(self, bbox_key: str) -> Optional[Dict[str, Any]]:
        """Load cached Overpass JSON response if available and recent (< 7 days old)."""
        cache_dir = settings.get_raw_dir("osm")
        bbox_hash = hashlib.md5(bbox_key.encode("utf-8")).hexdigest()[:10]
        file_path = cache_dir / f"overpass_{bbox_hash}.json"
        if file_path.exists():
            try:
                # Check modification time
                mtime = file_path.stat().st_mtime
                age_days = (time.time() - mtime) / (86400)
                if age_days < 7.0:
                    return json.loads(file_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.debug("Error reading OSM cache: %s", e)
        return None
