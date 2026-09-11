"""Expose metrics only for the provenance-checked artifact used for inference."""
import json
from pathlib import Path
from fastapi import APIRouter
from app.config import settings
from app.schemas.system import ModelMetricsResponse
from ml.training.train import load_classifier_pipeline
router = APIRouter()

@router.get("/model/metrics", response_model=ModelMetricsResponse)
def get_model_metrics():
    path = Path(settings.ml_artifacts_dir)
    try:
        model = load_classifier_pipeline(str(path / "fire_classifier.joblib"))
        card = json.loads((path / "model_card.json").read_text(encoding="utf-8"))
        return ModelMetricsResponse(status="ready", active_model_name=card["model_name"],
            algorithm=card["algorithm"], version=card["version"],
            evaluation_metrics=card.get("evaluation_metrics", {}),
            feature_importances=model.get_feature_importances(), model_card=card)
    except (FileNotFoundError, ValueError, KeyError):
        return ModelMetricsResponse(status="not_trained", active_model_name="No verified model installed",
            algorithm="none", version="0", evaluation_metrics={}, feature_importances={}, model_card=None)
