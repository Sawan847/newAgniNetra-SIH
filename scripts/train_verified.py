"""Train using reviewed observed features, never raw FIRMS confidence as labels.

Usage: python scripts/train_verified.py path/to/verified_features.csv
Required metadata: event_id, acq_date, spatial_group, verified_class,
label_source, reviewer_name, evidence_reference, feature_schema_version.
The remaining columns must be the features in ml/config.py. Blank values are missing.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]
from ml.config import FEATURE_COLUMNS, FIRE_CLASSES
from ml.training.train import run_model_comparison_and_training


def validate_training_frame(data):
    metadata = ["event_id", "acq_date", "spatial_group", "verified_class", "label_source",
                "reviewer_name", "evidence_reference", "feature_schema_version"]
    missing = set(metadata + FEATURE_COLUMNS) - set(data.columns)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    if data["event_id"].duplicated().any():
        raise ValueError("Duplicate event IDs: one reviewed label per observed detection is required")
    if not data["feature_schema_version"].eq(2).all():
        raise ValueError("Recompute observed features using schema v2")
    if not data["label_source"].eq("analyst_verified").all():
        raise ValueError("Synthetic and weak-rule labels cannot train the operational artifact")
    for field in metadata:
        if data[field].isna().any() or data[field].astype(str).str.strip().eq("").any():
            raise ValueError(f"Missing reference metadata: {field}")
    if set(data["verified_class"]) - set(FIRE_CLASSES):
        raise ValueError("Unknown classification label")
    data = data[data["verified_class"] != "uncertain"].copy()
    if len(data) < 100 or data["spatial_group"].nunique() < 3:
        raise ValueError("Collect at least 100 reviewed observations across at least 3 independent groups")
    counts = data["verified_class"].value_counts()
    if any(counts.get(label, 0) < 10 for label in FIRE_CLASSES[:-1]):
        raise ValueError("At least 10 reviewed examples are needed for each of the five known classes")
    dates = pd.to_datetime(data["acq_date"], errors="raise", utc=True)
    if dates.nunique() < 5:
        raise ValueError("At least five acquisition dates are required for chronological evaluation")
    for feature in FEATURE_COLUMNS:
        data[feature] = pd.to_numeric(data[feature], errors="raise")
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "ml" / "artifacts")
    args = parser.parse_args()
    data = validate_training_frame(pd.read_csv(args.csv))
    result = run_model_comparison_and_training(data[FEATURE_COLUMNS + ["acq_date"]],
        data["verified_class"], data["spatial_group"].to_numpy(), str(args.output))
    path = Path(result["model_card_path"])
    card = json.loads(path.read_text(encoding="utf-8"))
    card.update(training_data_source="analyst_verified_observations", feature_schema_version=2,
        training_file_sha256=hashlib.sha256(args.csv.read_bytes()).hexdigest(),
        reviewed_observations=len(data), independent_groups=int(data["spatial_group"].nunique()),
        limitations=["Labels and evidence references still require human audit",
          "Zero imputation is internal to the model; missing observations remain null in storage",
          "Holdout metrics do not establish deployment safety or accident confirmation",
          "WorldCover is 2021 land cover; OSM and cloud-free imagery coverage are incomplete"])
    path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    print(f"Trained {result['best_algorithm']}. Holdout macro F1: {result['best_macro_f1']:.4f}")
    print(f"Model card: {path}")

if __name__ == "__main__":
    main()
