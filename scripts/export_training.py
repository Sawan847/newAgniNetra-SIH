"""Export reviewed detections and schema-v2 observed features for training.

Usage: python scripts/export_training.py data/processed/verified_features.csv
Review spatial_group values: all observations from a facility or incident must
share one group, even when they span a geographic grid boundary.
"""
import csv
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from app.database import SessionLocal
from app.models.hotspot import Hotspot
from app.models.feedback import AnalystFeedback
from ml.config import FEATURE_COLUMNS
import app.models


def main():
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/processed/verified_features.csv"
    rows = []
    with SessionLocal() as db:
        labels = db.query(AnalystFeedback).filter_by(label_source="analyst_verified").order_by(AnalystFeedback.created_at.desc()).all()
        seen = set()
        for label in labels:
            if label.hotspot_id in seen:
                continue
            seen.add(label.hotspot_id)
            hotspot = db.get(Hotspot, label.hotspot_id) if label.hotspot_id else None
            if hotspot is None or str(hotspot.source or "").startswith("DEMO") or not hotspot.features:
                continue
            features = max(hotspot.features, key=lambda f: f.computed_at)
            if not features.extra_features or features.extra_features.get("distance_unit") != "km":
                continue
            row = {name: getattr(features, name, getattr(hotspot, name, None)) for name in FEATURE_COLUMNS}
            row.update(brightness=hotspot.brightness, bright_ti4=hotspot.bright_ti4, bright_ti5=hotspot.bright_ti5,
                brightness_delta=hotspot.bright_ti4-hotspot.bright_ti5 if hotspot.bright_ti4 is not None and hotspot.bright_ti5 is not None else None,
                frp=hotspot.frp, confidence=hotspot.confidence,
                event_id=hotspot.event_id or str(hotspot.id), acq_date=hotspot.acq_date,
                spatial_group=f"grid_{int(hotspot.latitude*10)}_{int(hotspot.longitude*10)}",
                verified_class=label.verified_class, label_source=label.label_source,
                reviewer_name=label.reviewer_name,
                evidence_reference=(label.evidence or {}).get("reference", label.notes or ""), feature_schema_version=2)
            rows.append(row)
    if not rows:
        raise SystemExit("No analyst-verified observations with current features. Import, enrich and review data first.")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} reviewed observations to {output}; audit spatial groups before training.")

if __name__ == "__main__":
    main()
