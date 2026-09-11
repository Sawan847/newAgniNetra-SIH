from enum import Enum
from typing import Dict, Any


class ThermalClass(str, Enum):
    INDUSTRIAL_FIRE = "industrial_fire"
    GAS_FLARE = "gas_flare"
    PERSISTENT_INDUSTRIAL_HEAT = "persistent_industrial_heat"
    WILDFIRE = "wildfire"
    AGRICULTURAL_BURNING = "agricultural_burning"
    MINING_ACTIVITY = "mining_activity"
    UNKNOWN = "unknown"


def classify_with_context(
    ml_prediction: str | None,
    ml_probability: float | None,
    context: Dict[str, Any],
) -> Dict[str, Any]:

    industrial_distance = context.get("industrial_distance_m")
    landcover = str(context.get("landcover", "")).lower()

    detections_7d = context.get("detections_7d", 0)
    active_days_30d = context.get("active_days_30d", 0)

    frp = context.get("frp", 0) or 0
    confidence = context.get("confidence", 0) or 0

    reasons = []

    # ---------------------------------------------------------
    # 1. Strong ML prediction
    # ---------------------------------------------------------
    if ml_prediction and (ml_probability or 0) >= 0.75:
        predicted_class = ml_prediction

        reasons.append(
            f"ML classifier confidence: {(ml_probability or 0) * 100:.1f}%"
        )

    else:
        predicted_class = ThermalClass.UNKNOWN.value

    # ---------------------------------------------------------
    # 2. Industrial infrastructure evidence
    # ---------------------------------------------------------
    near_industry = (
        industrial_distance is not None
        and industrial_distance <= 2000
    )

    if near_industry:
        reasons.append(
            f"Industrial infrastructure detected "
            f"{industrial_distance:.0f} m from hotspot"
        )

    # ---------------------------------------------------------
    # 3. Persistent thermal-source detection
    # ---------------------------------------------------------
    persistent = (
        detections_7d >= 4 or
        active_days_30d >= 8
    )

    if persistent and near_industry:
        predicted_class = ThermalClass.PERSISTENT_INDUSTRIAL_HEAT.value

        reasons.append(
            "Thermal anomaly repeatedly detected at the same "
            "industrial location"
        )

    # ---------------------------------------------------------
    # 4. Land-cover evidence
    # ---------------------------------------------------------
    forest_terms = [
        "forest",
        "wood",
        "woodland",
        "scrub"
    ]

    agricultural_terms = [
        "farmland",
        "farm",
        "crop",
        "agriculture"
    ]

    mining_terms = [
        "quarry",
        "mine",
        "mining"
    ]

    if any(term in landcover for term in forest_terms) and not near_industry:
        predicted_class = ThermalClass.WILDFIRE.value
        reasons.append("Hotspot lies within forest/natural vegetation")

    elif any(term in landcover for term in agricultural_terms):
        predicted_class = ThermalClass.AGRICULTURAL_BURNING.value
        reasons.append("Hotspot is located in agricultural land")

    elif any(term in landcover for term in mining_terms):
        predicted_class = ThermalClass.MINING_ACTIVITY.value
        reasons.append("Hotspot is located near mining/quarry land")

    # ---------------------------------------------------------
    # 5. Industrial fire indication
    # ---------------------------------------------------------
    if (
        near_industry
        and not persistent
        and frp >= 20
        and confidence >= 60
    ):
        predicted_class = ThermalClass.INDUSTRIAL_FIRE.value

        reasons.append(
            "High-energy thermal anomaly detected close to "
            "industrial infrastructure"
        )

    # ---------------------------------------------------------
    # Final confidence
    # ---------------------------------------------------------
    final_confidence = ml_probability or 0.50

    if near_industry:
        final_confidence += 0.08

    if persistent:
        final_confidence += 0.08

    final_confidence = min(final_confidence, 0.99)

    return {
        "classification": predicted_class,
        "confidence": round(final_confidence, 3),
        "persistent_source": persistent,
        "near_industry": near_industry,
        "evidence": reasons,
    }