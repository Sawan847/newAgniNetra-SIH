"""
Feature engineering utilities for AgniNetra.

This module converts raw NASA FIRMS thermal information and contextual
GIS information into clean numeric features that can be used by the
machine-learning pipeline.

Contextual information includes:

- Thermal characteristics
- Industrial proximity
- Forest proximity
- Land-cover information
- Historical/persistent thermal activity
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional


# ============================================================
# Helper functions
# ============================================================

def _safe_float(
    value: Any,
    default: float = 0.0
) -> float:
    """
    Convert a value to float safely.

    If the value is None, empty, or invalid,
    the supplied default value is returned.
    """

    if value is None:
        return default

    if isinstance(value, str):
        value = value.strip()

        if value == "":
            return default

        # FIRMS confidence may occasionally be represented
        # using strings rather than purely numeric values.
        confidence_mapping = {
            "low": 30.0,
            "nominal": 60.0,
            "high": 90.0,
            "l": 30.0,
            "n": 60.0,
            "h": 90.0,
        }

        lower_value = value.lower()

        if lower_value in confidence_mapping:
            return confidence_mapping[lower_value]

    try:
        return float(value)

    except (TypeError, ValueError):
        return default


def _safe_int(
    value: Any,
    default: int = 0
) -> int:
    """
    Convert a value to integer safely.
    """

    if value is None:
        return default

    try:
        return int(float(value))

    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any) -> bool:
    """
    Convert different value formats into Boolean values.
    """

    if isinstance(value, bool):
        return value

    if value is None:
        return False

    if isinstance(value, (int, float)):
        return value != 0

    if isinstance(value, str):

        return value.strip().lower() in {
            "true",
            "1",
            "yes",
            "y",
            "industrial",
        }

    return bool(value)


def _get_value(
    source: Any,
    key: str,
    default: Any = None
) -> Any:
    """
    Safely retrieve a value from either:

    - dictionary
    - Pydantic object
    - SQLAlchemy model
    - normal Python object
    """

    if source is None:
        return default

    if isinstance(source, Mapping):
        return source.get(key, default)

    return getattr(source, key, default)


# ============================================================
# Land-cover helpers
# ============================================================

def normalise_landcover(
    landcover: Optional[str]
) -> str:
    """
    Normalize land-cover text so that different GIS providers
    can be interpreted consistently.
    """

    if not landcover:
        return "unknown"

    value = str(landcover).strip().lower()

    # Industrial areas
    industrial_terms = (
        "industrial",
        "factory",
        "refinery",
        "power plant",
        "petrochemical",
        "steel",
        "terminal",
    )

    if any(term in value for term in industrial_terms):
        return "industrial"

    # Forest / natural vegetation
    forest_terms = (
        "forest",
        "wood",
        "woodland",
        "scrub",
        "vegetation",
    )

    if any(term in value for term in forest_terms):
        return "forest"

    # Agriculture
    agricultural_terms = (
        "farm",
        "farmland",
        "crop",
        "agriculture",
        "agricultural",
        "plantation",
    )

    if any(term in value for term in agricultural_terms):
        return "agricultural"

    # Mining
    mining_terms = (
        "mine",
        "mining",
        "quarry",
    )

    if any(term in value for term in mining_terms):
        return "mining"

    # Urban / built-up
    urban_terms = (
        "urban",
        "residential",
        "commercial",
        "built",
    )

    if any(term in value for term in urban_terms):
        return "urban"

    return value


# ============================================================
# Context feature engineering
# ============================================================

def build_context_features(
    brightness: float = 0,
    bright_t31: float = 0,
    frp: float = 0,
    confidence: float = 0,
    industrial_distance_m: float = 999999,
    forest_distance_m: float = 999999,
    detections_7d: int = 0,
    active_days_30d: int = 0,
    is_industrial_land: bool = False,
    is_forest_land: bool = False,
    is_agricultural_land: bool = False,
    is_mining_land: bool = False,
) -> Dict[str, float]:
    """
    Build contextual ML features for a thermal anomaly.

    These features combine NASA FIRMS thermal information with
    GIS/land-cover and historical information.

    This makes AgniNetra different from a normal FIRMS hotspot
    visualisation system.
    """

    brightness = _safe_float(brightness)

    bright_t31 = _safe_float(bright_t31)

    frp = _safe_float(frp)

    confidence = _safe_float(confidence)

    industrial_distance_m = _safe_float(
        industrial_distance_m,
        999999.0
    )

    forest_distance_m = _safe_float(
        forest_distance_m,
        999999.0
    )

    detections_7d = _safe_int(detections_7d)

    active_days_30d = _safe_int(active_days_30d)

    # --------------------------------------------------------
    # Derived proximity features
    # --------------------------------------------------------

    near_industry_500m = int(
        industrial_distance_m <= 500
    )

    near_industry_2km = int(
        industrial_distance_m <= 2000
    )

    near_industry_5km = int(
        industrial_distance_m <= 5000
    )

    near_forest_2km = int(
        forest_distance_m <= 2000
    )

    # --------------------------------------------------------
    # Persistent thermal-source feature
    # --------------------------------------------------------

    persistent_source = int(
        detections_7d >= 4
        or active_days_30d >= 8
    )

    # --------------------------------------------------------
    # Thermal-strength indicators
    # --------------------------------------------------------

    high_frp = int(
        frp >= 20
    )

    very_high_frp = int(
        frp >= 50
    )

    high_confidence = int(
        confidence >= 60
    )

    return {

        # ====================================================
        # NASA FIRMS / thermal features
        # ====================================================

        "brightness": brightness,

        "bright_t31": bright_t31,

        "frp": frp,

        "confidence": confidence,

        # ====================================================
        # GIS proximity features
        # ====================================================

        "industrial_distance_m":
            industrial_distance_m,

        "forest_distance_m":
            forest_distance_m,

        "near_industry_500m":
            near_industry_500m,

        "near_industry_2km":
            near_industry_2km,

        "near_industry_5km":
            near_industry_5km,

        "near_forest_2km":
            near_forest_2km,

        # ====================================================
        # Temporal / persistence features
        # ====================================================

        "detections_7d":
            detections_7d,

        "active_days_30d":
            active_days_30d,

        "persistent_source":
            persistent_source,

        # ====================================================
        # Land-cover features
        # ====================================================

        "is_industrial_land":
            int(_safe_bool(is_industrial_land)),

        "is_forest_land":
            int(_safe_bool(is_forest_land)),

        "is_agricultural_land":
            int(_safe_bool(is_agricultural_land)),

        "is_mining_land":
            int(_safe_bool(is_mining_land)),

        # ====================================================
        # Derived thermal indicators
        # ====================================================

        "high_frp":
            high_frp,

        "very_high_frp":
            very_high_frp,

        "high_confidence":
            high_confidence,
    }


# ============================================================
# Main feature extraction function
# ============================================================

def extract_full_feature_vector(
    thermal_data: Any = None,
    context_data: Any = None,
    **kwargs: Any,
) -> Dict[str, float]:
    """
    Create the complete feature vector used by AgniNetra.

    Parameters
    ----------
    thermal_data:
        FIRMS hotspot data. It may be a dictionary,
        Pydantic object, SQLAlchemy object, etc.

    context_data:
        GIS / contextual information such as industrial
        distance, forest distance and land-cover information.

    kwargs:
        Individual features can also be supplied directly.

    Returns
    -------
    Dict[str, float]

        Clean numerical feature dictionary ready for the
        prediction pipeline.
    """

    # --------------------------------------------------------
    # NASA FIRMS values
    # --------------------------------------------------------

    brightness = kwargs.get(
        "brightness",
        _get_value(
            thermal_data,
            "brightness",
            0
        )
    )

    bright_t31 = kwargs.get(
        "bright_t31",
        _get_value(
            thermal_data,
            "bright_t31",
            0
        )
    )

    frp = kwargs.get(
        "frp",
        _get_value(
            thermal_data,
            "frp",
            0
        )
    )

    confidence = kwargs.get(
        "confidence",
        _get_value(
            thermal_data,
            "confidence",
            0
        )
    )

    # --------------------------------------------------------
    # Industrial proximity
    # --------------------------------------------------------

    industrial_distance_m = kwargs.get(
        "industrial_distance_m",
        _get_value(
            context_data,
            "industrial_distance_m",
            999999
        )
    )

    # Support alternate name that may be returned
    # by another GIS service.

    if industrial_distance_m == 999999:

        industrial_distance_m = _get_value(
            context_data,
            "distance_to_industry_m",
            999999
        )

    # --------------------------------------------------------
    # Forest proximity
    # --------------------------------------------------------

    forest_distance_m = kwargs.get(
        "forest_distance_m",
        _get_value(
            context_data,
            "forest_distance_m",
            999999
        )
    )

    if forest_distance_m == 999999:

        forest_distance_m = _get_value(
            context_data,
            "distance_to_forest_m",
            999999
        )

    # --------------------------------------------------------
    # Historical detection information
    # --------------------------------------------------------

    detections_7d = kwargs.get(
        "detections_7d",
        _get_value(
            context_data,
            "detections_7d",
            0
        )
    )

    active_days_30d = kwargs.get(
        "active_days_30d",
        _get_value(
            context_data,
            "active_days_30d",
            0
        )
    )

    # --------------------------------------------------------
    # Land-cover information
    # --------------------------------------------------------

    landcover = kwargs.get(
        "landcover",
        _get_value(
            context_data,
            "landcover",
            "unknown"
        )
    )

    landcover = normalise_landcover(
        landcover
    )

    # Prefer explicitly supplied Boolean values.
    # Otherwise derive them from land-cover.

    is_industrial_land = kwargs.get(
        "is_industrial_land",
        _get_value(
            context_data,
            "is_industrial_land",
            landcover == "industrial"
        )
    )

    is_forest_land = kwargs.get(
        "is_forest_land",
        _get_value(
            context_data,
            "is_forest_land",
            landcover == "forest"
        )
    )

    is_agricultural_land = kwargs.get(
        "is_agricultural_land",
        _get_value(
            context_data,
            "is_agricultural_land",
            landcover == "agricultural"
        )
    )

    is_mining_land = kwargs.get(
        "is_mining_land",
        _get_value(
            context_data,
            "is_mining_land",
            landcover == "mining"
        )
    )

    # --------------------------------------------------------
    # Build feature dictionary
    # --------------------------------------------------------

    features = build_context_features(

        brightness=brightness,

        bright_t31=bright_t31,

        frp=frp,

        confidence=confidence,

        industrial_distance_m=
            industrial_distance_m,

        forest_distance_m=
            forest_distance_m,

        detections_7d=
            detections_7d,

        active_days_30d=
            active_days_30d,

        is_industrial_land=
            is_industrial_land,

        is_forest_land=
            is_forest_land,

        is_agricultural_land=
            is_agricultural_land,

        is_mining_land=
            is_mining_land,
    )

    return features


# ============================================================
# Convenience function for FIRMS records
# ============================================================

def extract_firms_features(
    firms_record: Any
) -> Dict[str, float]:
    """
    Extract the core NASA FIRMS thermal features.

    Useful when contextual GIS information has not yet
    been collected.
    """

    return build_context_features(

        brightness=_get_value(
            firms_record,
            "brightness",
            0
        ),

        bright_t31=_get_value(
            firms_record,
            "bright_t31",
            0
        ),

        frp=_get_value(
            firms_record,
            "frp",
            0
        ),

        confidence=_get_value(
            firms_record,
            "confidence",
            0
        ),
    )