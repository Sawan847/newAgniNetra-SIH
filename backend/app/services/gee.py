"""AgniNetra AI — Google Earth Engine & Satellite Spectral Service.

Integrates Sentinel-2 Surface Reflectance imagery and ESA WorldCover land classification.
Calculates observed pre-event indices (NDVI, NBR, NDMI). Missing imagery
and retrospective delta-NBR are explicitly unavailable.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, Optional, Tuple


from app.config import settings

logger = logging.getLogger(__name__)

# Try importing Google Earth Engine API
try:
    import ee
    EE_AVAILABLE = True
except ImportError:
    EE_AVAILABLE = False
    logger.info("earthengine-api not installed. Satellite feature extractor will report imagery as unavailable.")


class SatelliteFeatureService:
    """Service for extracting Sentinel-2 surface reflectance and land-cover indices."""

    def __init__(self):
        self._ee_initialized = False
        self._init_earth_engine()

    def _init_earth_engine(self) -> None:
        """Attempt to authenticate and initialize Google Earth Engine."""
        if not EE_AVAILABLE:
            return

        try:
            if settings.ee_service_account and settings.ee_private_key:
                credentials = ee.ServiceAccountCredentials(
                    settings.ee_service_account, key_data=settings.ee_private_key
                )
                ee.Initialize(credentials, project=settings.ee_project_id or None)
                self._ee_initialized = True
                logger.info("Google Earth Engine initialized via Service Account credentials.")
            elif settings.ee_project_id:
                ee.Initialize(project=settings.ee_project_id)
                self._ee_initialized = True
                logger.info("Google Earth Engine initialized via default project credentials.")
        except Exception as e:
            logger.warning("Google Earth Engine initialization skipped (%s). Imagery will be unavailable.", e)
            self._ee_initialized = False

    def is_gee_active(self) -> bool:
        """Check if live Google Earth Engine connection is available."""
        return self._ee_initialized

    def extract_spectral_features(
        self,
        lat: float,
        lon: float,
        acq_date: Optional[datetime.date] = None,
        land_cover_class: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Extract NDVI, NBR, NDMI, Delta-NBR, and cloud fraction for a coordinate and date.

        If GEE is live, queries Sentinel-2 SR collection with SCL cloud masking.
        Otherwise, returns null values with explicit missing-data provenance.
        """
        acq_date = acq_date or datetime.date.today()

        if self._ee_initialized:
            try:
                return self._query_gee_sentinel2(lat, lon, acq_date)
            except Exception as exc:
                logger.warning("Live GEE query failed for (%f, %f): %s. Imagery will be unavailable.", lat, lon, exc)

        return {"ndvi_value": None, "nbr_value": None, "ndmi_value": None,
                "delta_nbr": None, "cloud_cover_fraction": None,
                "imagery_available": False, "data_source": "UNAVAILABLE",
                "imagery_timestamp": None}

    def _query_gee_sentinel2(
        self, lat: float, lon: float, acq_date: datetime.date
    ) -> Dict[str, Any]:
        """Execute server-side Earth Engine query for Sentinel-2 SR harmonized imagery."""
        point = ee.Geometry.Point([lon, lat])
        date_obj = ee.Date(acq_date.strftime("%Y-%m-%d"))

        # Pre-fire window: 30 to 5 days before
        pre_start = date_obj.advance(-30, "day")
        pre_end = date_obj.advance(-5, "day")

        def mask_s2_clouds(image):
            scl = image.select("SCL")
            # Clear pixels: 4 (vegetation), 5 (bare soil), 6 (water), 7 (unclassified)
            clear_mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6)).Or(scl.eq(7))
            return image.updateMask(clear_mask).divide(10000.0)

        # Retrieve images
        s2_collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")

        pre_img = (
            s2_collection.filterBounds(point)
            .filterDate(pre_start, pre_end)
            .map(mask_s2_clouds)
            .median()
        )

        # Compute indices: NDVI = (B8-B4)/(B8+B4), NBR = (B8-B12)/(B8+B12), NDMI = (B8-B11)/(B8+B11)
        pre_ndvi = pre_img.normalizedDifference(["B8", "B4"]).rename("ndvi")
        pre_nbr = pre_img.normalizedDifference(["B8", "B12"]).rename("nbr")
        pre_ndmi = pre_img.normalizedDifference(["B8", "B11"]).rename("ndmi")

        combined = pre_ndvi.addBands([pre_nbr, pre_ndmi])
        sampled = combined.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=point.buffer(100),
            scale=20,
        ).getInfo()

        ndvi_val = sampled.get("ndvi")
        nbr_val = sampled.get("nbr")
        ndmi_val = sampled.get("ndmi")
        dnbr_val = sampled.get("delta_nbr")

        return {
            "ndvi_value": round(float(ndvi_val), 4) if ndvi_val is not None else None,
            "nbr_value": round(float(nbr_val), 4) if nbr_val is not None else None,
            "ndmi_value": round(float(ndmi_val), 4) if ndmi_val is not None else None,
            "delta_nbr": round(float(dnbr_val), 4) if dnbr_val is not None else None,
            "cloud_cover_fraction": None,
            "imagery_available": any(v is not None for v in (ndvi_val, nbr_val, ndmi_val)),
            "data_source": "GEE_SENTINEL_2",
            "imagery_timestamp": None,
            "window_start": (acq_date - datetime.timedelta(days=30)).isoformat(),
            "window_end_exclusive": (acq_date - datetime.timedelta(days=5)).isoformat(),
            "delta_nbr_status": "Requires separate retrospective before/after analysis",
        }


    def extract_land_cover(self, lat: float, lon: float) -> dict:
        """Sample the observed ESA WorldCover 2021 v200 Map band at 10 m."""
        if self._ee_initialized:
            try:
                value = (ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")
                         .reduceRegion(ee.Reducer.first(), ee.Geometry.Point([lon, lat]), 10)
                         .getInfo().get("Map"))
                if value is not None:
                    return {"land_cover_class": int(value), "source": "ESA_WORLDCOVER_2021_V200", "year": 2021}
            except Exception:
                logger.warning("WorldCover sample unavailable")
        return {"land_cover_class": None, "source": "UNAVAILABLE", "year": None}
