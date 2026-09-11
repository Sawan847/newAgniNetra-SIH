"""AgniNetra AI — NASA FIRMS Integration Service.

Handles Area API queries for VIIRS sensors (SNPP, NOAA-20, NOAA-21) with:
- Bounding box and date-range batching (<= 5 days per request)
- Resilient retries with exponential backoff
- Raw CSV payload archiving in data/raw/firms
- Strict schema validation and deterministic event ID creation
- Safe error handling without leaking MAP_KEY
"""

from __future__ import annotations

import csv
import datetime
import hashlib
import io
import logging
import math
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.config import settings
from app.services.geometry import validate_bbox

logger = logging.getLogger(__name__)

# The FIRMS MAP_KEY travels inside the URL path, not a header. httpx logs every
# request line at INFO ("HTTP Request: GET <full url> ..."), so enabling INFO logging
# anywhere in the process printed the raw key to the console and into any log file,
# defeating the masking this module does on its own log lines. Any secret carried in
# a URL path leaks exactly this way.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Supported NASA FIRMS NRT VIIRS sources
FIRMS_NRT_SOURCES = [
    "VIIRS_SNPP_NRT",
    "VIIRS_NOAA20_NRT",
    "VIIRS_NOAA21_NRT",
]

# Standard-processing archive products. VIIRS_SNPP_SP reaches back to 2012,
# MODIS_SP to 2000.
#
# These matter more than the NRT feed for this problem statement. India's fire
# regime is strongly seasonal - paddy residue burns Oct-Nov, wheat residue Apr-May,
# forest fires Feb-Jun - and NRT retains only about two months. A live pull landing
# in the monsoon contains almost no agricultural or vegetation fire at all, so
# demonstrating those classes at all requires the archive.
FIRMS_SP_SOURCES = [
    "VIIRS_SNPP_SP",
    "VIIRS_NOAA20_SP",
    "MODIS_SP",
]

SUPPORTED_FIRMS_SOURCES = FIRMS_NRT_SOURCES + FIRMS_SP_SOURCES

# Required columns in FIRMS VIIRS CSV responses
REQUIRED_CSV_COLUMNS = [
    "latitude",
    "longitude",
    "bright_ti4",
    "scan",
    "track",
    "acq_date",
    "acq_time",
    "satellite",
    "instrument",
    "confidence",
    "version",
    "bright_ti5",
    "frp",
    "daynight",
]


def mask_key_in_url(url: str, key: str) -> str:
    """Mask FIRMS Map Key in URL strings for safe logging."""
    if key and key in url:
        return url.replace(key, "******")
    return url


def generate_event_id(satellite: str, lat: float, lon: float, acq_date: str, acq_time: str) -> str:
    """Create a stable, unique event identifier for deduplication."""
    clean_sat = (satellite or "SAT").strip().upper()
    clean_time = (acq_time or "0000").strip().zfill(4)
    raw = f"{clean_sat}_{lat:.4f}_{lon:.4f}_{acq_date}_{clean_time}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
    return f"firms_{clean_sat}_{acq_date.replace('-', '')}_{clean_time}_{digest}"


class FIRMSClient:
    """Client for interacting with the NASA FIRMS Area API."""

    def __init__(
        self,
        map_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        self.map_key = (map_key or settings.effective_firms_map_key).strip()
        self.base_url = (base_url or settings.firms_base_url).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries

    def is_configured(self) -> bool:
        """Check if a valid MAP_KEY is configured."""
        return bool(self.map_key and len(self.map_key) >= 16)

    def split_date_range(
        self, start_date: datetime.date, end_date: datetime.date, max_batch_days: int = 5
    ) -> List[Tuple[datetime.date, int]]:
        """Split a wide date range into chunks compatible with the 5-day FIRMS limit."""
        if start_date > end_date or not 1 <= max_batch_days <= 5:
            raise ValueError("Invalid FIRMS date range or batch size")
        batches = []
        curr = start_date
        while curr <= end_date:
            days_left = (end_date - curr).days + 1
            batch_days = min(days_left, max_batch_days)
            batches.append((curr, batch_days))
            curr += datetime.timedelta(days=batch_days)
        return batches

    def fetch_area_csv(
        self,
        source: str,
        bbox: Tuple[float, float, float, float],  # (min_lon, min_lat, max_lon, max_lat)
        start_date: datetime.date,
        day_range: int = 1,
    ) -> str:
        """Fetch raw CSV data from NASA FIRMS Area API with exponential backoff."""
        if not self.is_configured():
            logger.warning("NASA FIRMS MAP_KEY is not configured in environment.")
            raise RuntimeError("NASA FIRMS MAP_KEY is not configured. Set FIRMS_MAP_KEY in .env.")

        if source not in SUPPORTED_FIRMS_SOURCES:
            raise ValueError(f"Unsupported FIRMS source: {source}. Choose from {SUPPORTED_FIRMS_SOURCES}")

        validate_bbox(bbox)
        if not 1 <= day_range <= 5:
            raise ValueError("FIRMS day_range must be 1 to 5")
        min_lon, min_lat, max_lon, max_lat = bbox
        bbox_str = f"{min_lon},{min_lat},{max_lon},{max_lat}"
        date_str = start_date.strftime("%Y-%m-%d")

        # URL structure: https://firms.modaps.eosdis.nasa.gov/api/area/csv/[MAP_KEY]/[SOURCE]/[BBOX]/[DAY_RANGE]/[DATE]
        endpoint = f"{self.base_url}/csv/{self.map_key}/{source}/{bbox_str}/{day_range}/{date_str}"
        safe_url = mask_key_in_url(endpoint, self.map_key)

        headers = {"User-Agent": "AgniNetra-AI-Platform/0.1.0"}

        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info("Requesting FIRMS data: %s (attempt %d/%d)", safe_url, attempt, self.max_retries)
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.get(endpoint, headers=headers)

                if resp.status_code == 200:
                    csv_text = resp.text
                    self._cache_raw_response(source, date_str, bbox_str, csv_text)
                    return csv_text
                elif resp.status_code == 429:
                    wait_sec = attempt * 3
                    logger.warning("FIRMS API rate limited (429). Retrying in %ds...", wait_sec)
                    time.sleep(wait_sec)
                else:
                    logger.error("FIRMS API error HTTP %d on %s", resp.status_code, safe_url)
                    resp.raise_for_status()
            except Exception as exc:
                last_exc = exc
                wait_sec = attempt * 2
                logger.warning("FIRMS connection attempt %d failed: %s. Backing off %ds...", attempt, type(exc).__name__, wait_sec)
                time.sleep(wait_sec)

        if last_exc:
            raise RuntimeError(f"FIRMS request failed after {self.max_retries} attempts ({type(last_exc).__name__})") from None
        raise RuntimeError("FIRMS request exhausted retries, possibly rate limited")

    def build_area_url(self, source, bbox, start_date, day_range=1, mask_key=False):
        validate_bbox(bbox)
        key = "******" if mask_key else self.map_key
        area = ",".join(str(v) for v in bbox)
        return f"{self.base_url}/csv/{key}/{source}/{area}/{day_range}/{start_date.isoformat()}"

    def parse_firms_csv(self, csv_content: str, source_label: str = "FIRMS") -> List[Dict[str, Any]]:
        """Parse, validate, and convert raw FIRMS CSV text into standardized hotspot records."""
        if not csv_content or not csv_content.strip():
            raise ValueError("Empty FIRMS response; no valid CSV header received")

        # Check for error responses returned as text
        if "Invalid MAP_KEY" in csv_content or "Error:" in csv_content:
            raise ValueError("FIRMS rejected the request; check MAP_KEY and product availability")

        f = io.StringIO(csv_content)
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {"latitude", "longitude", "acq_date", "acq_time", "satellite", "frp"}.issubset(reader.fieldnames):
            raise ValueError("Invalid FIRMS CSV header")

        records = []
        for row_idx, row in enumerate(reader):
            try:
                # Safe coordinate parsing
                lat = float(row["latitude"])
                lon = float(row["longitude"])
                if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                    continue

                # Safe float parsing
                bright_ti4 = self._safe_float(row.get("bright_ti4"))
                bright_ti5 = self._safe_float(row.get("bright_ti5"))
                frp = self._safe_float(row.get("frp"))

                # Confidence
                conf_raw = row.get("confidence", "").strip().lower()
                conf_val: Optional[float] = None
                if conf_raw in ("l", "low"):
                    conf_val = 30.0
                elif conf_raw in ("n", "nominal"):
                    conf_val = 65.0
                elif conf_raw in ("h", "high"):
                    conf_val = 90.0
                else:
                    conf_val = self._safe_float(conf_raw)

                # Date and Time
                acq_date_str = row.get("acq_date", "").strip()
                acq_time_str = row.get("acq_time", "").strip().zfill(4)

                acq_date_obj = datetime.date.fromisoformat(acq_date_str)
                acq_time_obj = (
                    datetime.time(int(acq_time_str[:2]), int(acq_time_str[2:]))
                    if len(acq_time_str) == 4 and acq_time_str.isdigit()
                    else None
                )

                if acq_time_obj is None or frp is not None and frp < 0:
                    raise ValueError("Invalid acquisition time or FRP")

                satellite = row.get("satellite", "").strip()
                instrument = row.get("instrument", "").strip()
                daynight = row.get("daynight", "D").strip().upper()[:1]

                event_id = generate_event_id(satellite, lat, lon, acq_date_str, acq_time_str)

                record = {
                    "event_id": event_id,
                    "latitude": round(lat, 6),
                    "longitude": round(lon, 6),
                    "brightness": bright_ti4,
                    "bright_ti4": bright_ti4,
                    "bright_ti5": bright_ti5,
                    "frp": frp,
                    "confidence": conf_val,
                    "satellite": satellite,
                    "instrument": instrument,
                    "acq_date": acq_date_obj,
                    "acq_time": acq_time_obj,
                    "daynight": daynight,
                    "source": source_label,
                    # NASA's own coarse inference, present on the SP archive products and
                    # absent from NRT: 0 vegetation fire, 1 volcano, 2 other static land
                    # source, 3 offshore. Deliberately NOT a model feature and NOT a weak-label
                    # source - it is kept purely as an independent baseline to measure against.
                    # Training on NASA's guess and then scoring against it would be circular.
                    "firms_type": self._safe_float(row.get("type")),
                    "raw_data": dict(row),
                }
                records.append(record)
            except Exception as e:
                logger.debug("Skipping malformed FIRMS CSV row #%d: %s", row_idx, e)

        return records

    def _safe_float(self, value: Any) -> Optional[float]:
        """Convert string to float safely, returning None on failure."""
        if value is None:
            return None
        try:
            val_str = str(value).strip()
            if not val_str or val_str.lower() in ("nan", "null", "none"):
                return None
            number = float(val_str)
            return number if math.isfinite(number) else None
        except (ValueError, TypeError):
            return None

    def _cache_raw_response(self, source: str, date_str: str, bbox_str: str, content: str) -> Path:
        """Save raw CSV to data/raw/firms for lineage and auditing."""
        cache_dir = settings.get_raw_dir("firms")
        bbox_hash = hashlib.md5(bbox_str.encode("utf-8")).hexdigest()[:8]
        filename = f"{source}_{date_str}_{bbox_hash}.csv"
        file_path = cache_dir / filename
        file_path.write_text(content, encoding="utf-8")
        return file_path
