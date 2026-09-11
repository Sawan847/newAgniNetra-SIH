"""AgniNetra AI — Comprehensive Feature Engineering Module.

Computes thermal, spatial proximity, historical persistence, DBSCAN cluster spread,
and satellite spectral features for the two-stage fire classification engine.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN

from ml.config import FEATURE_COLUMNS


def compute_persistence_score(
    hotspots: pd.DataFrame,
    radius_km: float = 2.0,
    window_days: int = 7,
) -> pd.Series:
    """Count recurrence of thermal anomalies within a spatial radius over a temporal window."""
    if hotspots.empty:
        return pd.Series(dtype=float)

    result = np.zeros(len(hotspots), dtype=float)
    dates = pd.to_datetime(hotspots["acq_date"])
    lats = hotspots["latitude"].values
    lons = hotspots["longitude"].values

    for i in range(len(hotspots)):
        time_mask = (dates >= dates.iloc[i] - pd.Timedelta(days=window_days)) & (
            dates <= dates.iloc[i]
        )
        spatial_dist = _haversine_vectorized(lats[i], lons[i], lats, lons)
        nearby = (spatial_dist <= radius_km) & time_mask.values
        result[i] = max(int(nearby.sum()) - 1, 0)

    return pd.Series(result, index=hotspots.index, name=f"persistence_score_{window_days}d")


def compute_historical_frp_baselines(
    hotspots: pd.DataFrame,
    radius_km: float = 3.0,
    window_days: int = 90,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute historical median FRP, historical max FRP, and current-to-historical FRP ratio."""
    if hotspots.empty or "frp" not in hotspots.columns:
        empty = pd.Series(dtype=float)
        return empty, empty, empty

    n = len(hotspots)
    median_frp = np.zeros(n, dtype=float)
    max_frp = np.zeros(n, dtype=float)
    ratio_frp = np.ones(n, dtype=float)

    dates = pd.to_datetime(hotspots["acq_date"])
    lats = hotspots["latitude"].values
    lons = hotspots["longitude"].values
    frps = hotspots["frp"].fillna(0.0).values

    for i in range(n):
        time_mask = (dates >= dates.iloc[i] - pd.Timedelta(days=window_days)) & (
            dates < dates.iloc[i]  # strictly prior
        )
        spatial_dist = _haversine_vectorized(lats[i], lons[i], lats, lons)
        nearby_mask = (spatial_dist <= radius_km) & time_mask.values

        if nearby_mask.any():
            hist_vals = frps[nearby_mask]
            med = float(np.median(hist_vals))
            mx = float(np.max(hist_vals))
            median_frp[i] = round(med, 2)
            max_frp[i] = round(mx, 2)
            ratio_frp[i] = round(float(frps[i] / (med + 1e-3)), 2)
        else:
            median_frp[i] = round(float(frps[i]), 2)
            max_frp[i] = round(float(frps[i]), 2)
            ratio_frp[i] = 1.0

    return (
        pd.Series(median_frp, index=hotspots.index, name="historical_median_frp"),
        pd.Series(max_frp, index=hotspots.index, name="historical_max_frp"),
        pd.Series(ratio_frp, index=hotspots.index, name="frp_to_historical_ratio"),
    )


def compute_daynight_flag(hotspots: pd.DataFrame) -> pd.Series:
    """Convert FIRMS daynight column to boolean integer (1 for Night, 0 for Day)."""
    if "daynight" not in hotspots.columns:
        return pd.Series(0, index=hotspots.index, name="is_nighttime")
    return hotspots["daynight"].astype(str).str.upper().eq("N").astype(int).rename("is_nighttime")


def compute_day_of_year(hotspots: pd.DataFrame) -> pd.Series:
    """Extract day of year (1-366) from acquisition date."""
    if "acq_date" not in hotspots.columns:
        return pd.Series(1, index=hotspots.index, name="day_of_year")
    return pd.to_datetime(hotspots["acq_date"]).dt.dayofyear.rename("day_of_year")


def compute_cluster_spread_features(
    hotspots: pd.DataFrame,
    eps_km: float = 3.0,
    min_samples: int = 2,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Compute DBSCAN cluster size, spread radius (km), and principal elongation direction (deg)."""
    n = len(hotspots)
    if n == 0:
        empty = pd.Series(dtype=float)
        return empty, empty, empty

    coords = hotspots[["latitude", "longitude"]].values
    kms_per_radian = 6371.0088
    epsilon = eps_km / kms_per_radian

    rad_coords = np.radians(coords)
    db = DBSCAN(eps=epsilon, min_samples=min_samples, metric="haversine").fit(rad_coords)
    labels = db.labels_

    sizes = np.ones(n, dtype=int)
    spreads = np.zeros(n, dtype=float)
    directions = np.zeros(n, dtype=float)

    for i in range(n):
        lbl = labels[i]
        if lbl != -1:
            cluster_indices = np.where(labels == lbl)[0]
            c_coords = coords[cluster_indices]
            sizes[i] = len(cluster_indices)

            centroid = np.mean(c_coords, axis=0)
            dists = _haversine_vectorized(centroid[0], centroid[1], c_coords[:, 0], c_coords[:, 1])
            spreads[i] = round(float(np.max(dists)), 3)

            if len(cluster_indices) >= 2:
                d_lat = c_coords[:, 0] - centroid[0]
                d_lon = c_coords[:, 1] - centroid[1]
                cov = np.cov(d_lat, d_lon)
                if cov.shape == (2, 2):
                    eigvals, eigvecs = np.linalg.eigh(cov)
                    p_vec = eigvecs[:, np.argmax(eigvals)]
                    angle_deg = float(np.degrees(np.arctan2(float(p_vec[1]), float(p_vec[0]))) % 360.0)
                    directions[i] = round(angle_deg, 1)

    return (
        pd.Series(sizes, index=hotspots.index, name="cluster_size"),
        pd.Series(spreads, index=hotspots.index, name="cluster_spread_km"),
        pd.Series(directions, index=hotspots.index, name="cluster_direction_deg"),
    )


def extract_full_feature_vector(
    hotspot_record: Dict[str, Any],
    historical_hotspots: Optional[List[Dict[str, Any]]] = None,
    facilities: Optional[List[Dict[str, Any]]] = None,
    spectral_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Observed features only. Distances are kilometres; missing evidence stays null.

    Persistence counts distinct prior acquisition days within 1 km. Multiple
    satellites detecting the same site on one day do not create extra persistence.
    """
    from shapely.geometry import Point
    from shapely import wkt

    def number(value):
        try:
            result = float(value)
            return result if np.isfinite(result) else None
        except (TypeError, ValueError):
            return None

    def timestamp(record):
        date = record.get("acq_date")
        if isinstance(date, str):
            date = datetime.date.fromisoformat(date)
        if not isinstance(date, datetime.date):
            return None
        time = record.get("acq_time")
        if isinstance(time, str):
            time = datetime.time.fromisoformat(time) if ":" in time else datetime.time(int(time.zfill(4)[:2]), int(time.zfill(4)[2:]))
        return datetime.datetime.combine(date, time if isinstance(time, datetime.time) else datetime.time.min)

    lat, lon = float(hotspot_record["latitude"]), float(hotspot_record["longitude"])
    current = timestamp(hotspot_record)
    if current is None:
        raise ValueError("Acquisition date is required for historical features")
    features = {name: None for name in FEATURE_COLUMNS}
    ti4 = number(hotspot_record.get("bright_ti4", hotspot_record.get("brightness")))
    if ti4 is None:
        ti4 = number(hotspot_record.get("brightness"))
    ti5, frp = number(hotspot_record.get("bright_ti5")), number(hotspot_record.get("frp"))
    raw_conf = hotspot_record.get("confidence")
    categories = {"l": 30, "low": 30, "n": 65, "nominal": 65, "h": 90, "high": 90}
    conf = categories.get(str(raw_conf).lower(), number(raw_conf))
    features.update(brightness=ti4, bright_ti4=ti4, bright_ti5=ti5, frp=frp,
                    brightness_delta=ti4-ti5 if ti4 is not None and ti5 is not None else None,
                    confidence=conf, is_nighttime=hotspot_record.get("daynight") == "N",
                    day_of_year=current.timetuple().tm_yday)
    distances, mine_distances = [], []
    inside = False
    for facility in facilities or []:
        if facility.get("latitude") is None or facility.get("longitude") is None:
            continue
        distance = _haversine_single(lat, lon, facility["latitude"], facility["longitude"])
        distances.append(distance)
        if "min" in str(facility.get("facility_type", "")) or "quarry" in str(facility.get("facility_type", "")):
            mine_distances.append(distance)
        footprint = facility.get("footprint_wkt")
        if footprint:
            try:
                polygon = wkt.loads(footprint)
                inside = inside or (polygon.is_valid and polygon.covers(Point(lon, lat)))
            except Exception:
                pass
    features.update(dist_nearest_facility=min(distances) if distances else None,
                    is_inside_facility=inside,
                    nearby_facility_count_1km=sum(d <= 1 for d in distances),
                    nearby_facility_count_5km=sum(d <= 5 for d in distances),
                    dist_nearest_mine=min(mine_distances) if mine_distances else None)
    counts = {1: 0, 7: 0, 30: 0, 90: 0}
    days = {7: set(), 30: set()}
    hist_frps = []
    for history in historical_hotspots or []:
        observed = timestamp(history)
        if observed is None or observed >= current:
            continue
        elapsed = (current-observed).total_seconds() / 86400
        if elapsed > 90:
            continue
        if _haversine_single(lat, lon, history["latitude"], history["longitude"]) > 1:
            continue
        for window in counts:
            if elapsed <= window:
                counts[window] += 1
                if window in days:
                    days[window].add(observed.date())
        # Baselines compare the same sensor when that metadata is available.
        historical_frp = number(history.get("frp"))
        if historical_frp is not None and history.get("satellite") == hotspot_record.get("satellite"):
            hist_frps.append(historical_frp)
    median = float(np.median(hist_frps)) if hist_frps else None
    features.update(nearby_hotspot_count_24h=counts[1], nearby_hotspot_count_7d=counts[7],
                    nearby_hotspot_count_30d=counts[30], nearby_hotspot_count_90d=counts[90],
                    persistence_score=len(days[7]), persistence_score_30d=len(days[30]),
                    recurrence_rate=len(days[30])/30, historical_median_frp=median,
                    historical_max_frp=max(hist_frps) if hist_frps else None,
                    frp_to_historical_ratio=frp/median if median and frp is not None else None)
    spectral = spectral_data or {}
    for name in ("ndvi_value", "nbr_value", "ndmi_value", "delta_nbr", "cloud_cover_fraction"):
        features[name] = number(spectral.get(name))
    features["imagery_available"] = bool(spectral.get("imagery_available", False))
    features["land_cover_class"] = number(hotspot_record.get("land_cover_class"))
    return features


def _haversine_single(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance between two single points in kilometres."""
    r = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0) ** 2
    )
    return float(2.0 * r * np.arcsin(np.sqrt(a)))


def _haversine_vectorized(
    lat1: float, lon1: float, lat2: np.ndarray, lon2: np.ndarray
) -> np.ndarray:
    """Vectorized haversine distance in kilometres."""
    r = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2.0) ** 2
    )
    return 2.0 * r * np.arcsin(np.sqrt(a))
