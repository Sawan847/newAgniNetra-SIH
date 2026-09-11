"""Explainable Multi-Factor Risk Assessment Engine for AgniNetra AI."""

from __future__ import annotations

from typing import Any
from app.config import settings


def calculate_risk_score(
    frp: float | None,
    brightness: float | None,
    dist_facility_m: float | None,
    is_inside_facility: bool = False,
    persistence_count: int = 1,
    predicted_class: str | None = None,
    confidence: float | None = 0.5,
) -> dict[str, Any]:
    """Calculate an explainable composite risk score (0-100) based on physical factors.

    Components:
    1. Thermal Intensity (0-35 points): Evaluates Fire Radiative Power (MW) and brightness temp.
    2. Proximity & Containment (0-30 points): Evaluates proximity to OSM industrial infrastructure.
    3. Persistence & Recurrence (0-20 points): Temporal recurrence over 30 days.
    4. Hazard Classification Multiplier (0-15 points): Risk inherent to the predicted event class.

    Returns:
        Dict containing composite score, categorical level, individual factor contributions,
        and human-readable evidence explanations.
    """
    factors: list[dict[str, Any]] = []
    total_score = 0.0

    # 1. Thermal Intensity (Max 35 points)
    safe_frp = max(0.0, frp or 0.0)
    safe_bright = max(0.0, brightness or 300.0)

    # Base FRP scaling: 0-100 MW maps up to 25 pts, >100 MW adds up to 10 more
    frp_contrib = min(25.0, (safe_frp / 100.0) * 25.0)
    if safe_frp > 100.0:
        frp_contrib += min(10.0, ((safe_frp - 100.0) / 200.0) * 10.0)

    # Brightness temp bonus: >350K suggests very intense combustion
    bright_bonus = 0.0
    if safe_bright > 360.0:
        bright_bonus = 5.0
    elif safe_bright > 330.0:
        bright_bonus = 2.5

    thermal_score = min(35.0, round(frp_contrib + bright_bonus, 2))
    total_score += thermal_score
    factors.append({
        "factor": "Thermal Intensity & Energy Radiated",
        "category": "thermal",
        "contribution": thermal_score,
        "max_points": 35.0,
        "explanation": (
            f"FRP of {safe_frp:.1f} MW and brightness temperature of {safe_bright:.1f} K "
            f"indicate {'extreme' if thermal_score > 25 else 'moderate' if thermal_score > 12 else 'low'} "
            "radiative heat release."
        ),
    })

    # 2. Proximity & Containment (Max 30 points)
    if is_inside_facility:
        prox_score = 30.0
        prox_expl = "Hotspot is directly contained within a registered industrial facility perimeter."
    elif dist_facility_m is not None:
        if dist_facility_m <= 100:
            prox_score = 28.0
            prox_expl = f"Critical proximity: {dist_facility_m:.0f}m from mapped facility centre."
        elif dist_facility_m <= 500:
            prox_score = 20.0
            prox_expl = f"High proximity: {dist_facility_m:.0f}m from mapped facility centre."
        elif dist_facility_m <= 1500:
            prox_score = 12.0
            prox_expl = f"Moderate proximity: {dist_facility_m:.0f}m from industrial assets."
        elif dist_facility_m <= 5000:
            prox_score = 5.0
            prox_expl = f"Low proximity: {dist_facility_m / 1000:.1f}km from nearest mapped facility."
        else:
            prox_score = 1.0
            prox_expl = f"Isolated hotspot: {dist_facility_m / 1000:.1f}km from registered infrastructure."
    else:
        prox_score = 8.0
        prox_expl = "Infrastructure distance undetermined; defaulting to regional baseline risk."

    total_score += prox_score
    factors.append({
        "factor": "Infrastructure Proximity & Containment",
        "category": "spatial",
        "contribution": round(prox_score, 2),
        "max_points": 30.0,
        "explanation": prox_expl,
    })

    # 3. Persistence & Recurrence (Max 20 points)
    # 1 event = 3 pts (isolated), 2-4 events = 8 pts, 5-10 = 15 pts, >10 = 20 pts
    if persistence_count >= 10:
        persist_score = 20.0
        persist_expl = f"Chronic thermal signature: {persistence_count} detections in 30-day window (persistent industrial flare or chronic fire)."
    elif persistence_count >= 5:
        persist_score = 15.0
        persist_expl = f"Recurring thermal activity: {persistence_count} detections in past 30 days."
    elif persistence_count >= 2:
        persist_score = 8.0
        persist_expl = f"Multiple cluster detections ({persistence_count}) recorded in past 30 days."
    else:
        persist_score = 3.0
        persist_expl = "Single transient detection in current observation window."

    total_score += persist_score
    factors.append({
        "factor": "30-Day Persistence & Recurrence",
        "category": "temporal",
        "contribution": round(persist_score, 2),
        "max_points": 20.0,
        "explanation": persist_expl,
    })

    # 4. Classification Hazard Multiplier (Max 15 points)
    cls_weights: dict[str, float] = {
        "accidental_industrial_fire": 15.0,
        "persistent_industrial_source": 4.0,
        "forest_or_natural_fire": 12.0,
        "agricultural_burning": 6.0,
        "mining_or_other": 9.0,
        "uncertain": 0.0,
        "structural_fire": 15.0,
        "industrial_fire": 14.0,
        "wildfire": 12.0,
        "coal_mine_fire": 13.0,
        "gas_flare": 8.0,
        "agricultural_burn": 6.0,
        "biomass_burn": 5.0,
        "solar_farm_reflection": 1.0,
        "unknown": 7.0,
    }

    norm_class = (predicted_class or "unknown").lower().replace(" ", "_")
    base_cls_hazard = cls_weights.get(norm_class, 7.0)
    conf_factor = max(0.0, min(1.0, confidence if confidence is not None else 0.0))
    class_score = min(15.0, round(base_cls_hazard * conf_factor, 2))
    total_score += class_score

    factors.append({
        "factor": "Event Hazard Classification",
        "category": "classification",
        "contribution": class_score,
        "max_points": 15.0,
        "explanation": (
            f"Predicted class '{predicted_class or 'unassigned'}' carry hazard weight "
            f"{base_cls_hazard} weighted by model confidence {conf_factor * 100:.0f}%."
        ),
    })

    # Clamp total score between 0 and 100
    composite_score = round(min(100.0, max(0.0, total_score)), 1)

    # Determine risk level
    if composite_score >= settings.risk_critical_threshold:
        risk_level = "critical"
        recommendation = "Urgent analyst verification and facility contact recommended before any response decision."
    elif composite_score >= settings.risk_high_threshold:
        risk_level = "high"
        recommendation = "Priority analyst investigation required; verify Sentinel-2 imagery and check facility operational logs."
    elif composite_score >= settings.risk_medium_threshold:
        risk_level = "medium"
        recommendation = "Standard surveillance monitoring; review on next satellite pass."
    else:
        risk_level = "low"
        recommendation = "Routine thermal observation; no emergency escalation required."

    return {
        "method": "Unvalidated heuristic triage score; not an incident probability",
        "risk_score": composite_score,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "factors": factors,
    }
