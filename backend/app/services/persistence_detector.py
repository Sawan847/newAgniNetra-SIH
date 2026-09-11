from datetime import datetime, timedelta


def analyze_persistence(
    previous_detections,
    latitude: float,
    longitude: float,
):
    """
    Detect repeated thermal activity near the same location.

    previous_detections should contain:
        latitude
        longitude
        detected_at
    """

    recent_30d = []
    now = datetime.utcnow()

    # Approximate coordinate tolerance.
    # ~0.01 degree is roughly 1 km.
    tolerance = 0.01

    for detection in previous_detections:

        timestamp = detection.detected_at

        if timestamp < now - timedelta(days=30):
            continue

        lat_diff = abs(
            float(detection.latitude) - latitude
        )

        lon_diff = abs(
            float(detection.longitude) - longitude
        )

        if lat_diff <= tolerance and lon_diff <= tolerance:
            recent_30d.append(detection)

    seven_day_cutoff = now - timedelta(days=7)

    detections_7d = [
        d for d in recent_30d
        if d.detected_at >= seven_day_cutoff
    ]

    unique_days = {
        d.detected_at.date()
        for d in recent_30d
    }

    active_days_30d = len(unique_days)

    persistent = (
        len(detections_7d) >= 4
        or active_days_30d >= 8
    )

    return {
        "detections_7d": len(detections_7d),
        "detections_30d": len(recent_30d),
        "active_days_30d": active_days_30d,
        "persistent": persistent,
    }