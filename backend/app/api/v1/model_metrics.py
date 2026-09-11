"""Expose metrics for the model that is actually loaded and serving predictions.

The model card written by ml.training.train_pipeline is the source of truth. This
endpoint previously loaded `fire_classifier.joblib` via
ml.training.train.load_classifier_pipeline - the deprecated two-stage model trained
on synthetically generated features - so the dashboard reported figures for a model
that no longer performs inference.
"""

import json
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

from app.config import settings
from app.schemas.system import ModelMetricsResponse

router = APIRouter()


@router.get("/model/metrics", response_model=ModelMetricsResponse)
def get_model_metrics() -> ModelMetricsResponse:
    path = Path(settings.ml_artifacts_dir)
    card_path = path / "model_card.json"

    if not card_path.exists():
        return ModelMetricsResponse(
            status="not_trained",
            active_model_name="No model trained",
            algorithm="none",
            version="0",
            evaluation_metrics={},
            feature_importances={},
            model_card=None,
        )

    try:
        card: Dict[str, Any] = json.loads(card_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ModelMetricsResponse(
            status="not_trained",
            active_model_name="Model card unreadable",
            algorithm="none",
            version="0",
            evaluation_metrics={},
            feature_importances={},
            model_card=None,
        )

    selected = card.get("selected_model_metrics", {}) or {}
    comparison = card.get("algorithm_comparison", {}) or {}
    chosen = card.get("algorithm", "")
    chosen_cv = comparison.get(chosen, {}) or {}

    # Flattened for the dashboard tiles, using the names the frontend already reads.
    evaluation_metrics: Dict[str, Any] = {
        "macro_f1": selected.get("temporal_holdout_macro_f1"),
        "macro_f1_all_classes": selected.get("temporal_holdout_macro_f1_all_classes"),
        "mean_spatial_cv_f1": chosen_cv.get("spatial_cv_macro_f1_mean"),
        "abstain_rate": selected.get("abstain_rate"),
        "macro_f1_on_confident_subset": selected.get("macro_f1_on_confident_subset"),
        "per_class": selected.get("per_class", {}),
        "confusion_matrix": selected.get("confusion_matrix", {}),
        "n_features": card.get("n_features"),
        "classes": card.get("classes", []),
        # Provenance is surfaced deliberately. When the model was fitted on the
        # offline simulator rather than real observations, that must be visible on
        # screen rather than buried in a JSON file nobody opens.
        "data_provenance": card.get("data_provenance"),
        "label_coverage": card.get("label_coverage", {}),
        "feature_ablation": card.get("feature_ablation", {}),
        "holdout_class_coverage": card.get("holdout_class_coverage", {}),
        "label_circularity_note": card.get("label_circularity_note"),
        "known_limitations": card.get("known_limitations", []),
        "deliverable_i_segregation": card.get("deliverable_i_segregation", {}),
        "firms_type_baseline": card.get("firms_type_baseline"),
    }

    return ModelMetricsResponse(
        status="ready",
        active_model_name=card.get("model_name", "AgniNetra-ThermalClassifier"),
        algorithm=chosen or "unknown",
        version=card.get("version", "0"),
        evaluation_metrics=evaluation_metrics,
        # The deployed model is a RandomForest/LogisticRegression bundle without a
        # published importance vector; per-detection evidence is served by the
        # classifier service instead. Returning an empty map is honest - the old code
        # returned a uniform placeholder that looked like a real attribution.
        feature_importances={},
        model_card=card,
    )
