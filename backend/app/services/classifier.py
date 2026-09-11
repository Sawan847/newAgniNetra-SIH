"""AgniNetra AI - Inference service backed by the site-level classifier.

Bridges the database to ml.training.train_pipeline. The important property is that
this uses the *same* feature-engineering entry point as training
(ml.features.site_features.build_feature_frame), so a feature can never be computed
one way during training and another way at inference.

The previous implementation had exactly that bug: the trainer sampled cluster_size,
cluster_spread_km and cluster_direction_deg randomly while the inference path
hardcoded them to 1.0, 0.0 and 0.0. The model learned from three features that were
frozen constants in production.
"""

from __future__ import annotations

import datetime
import logging
import os
from typing import Any, Dict, List, Optional

import joblib
import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_ARTIFACT = os.path.join("ml", "artifacts", "thermal_classifier.joblib")

# How much history to pull around a detection when computing site persistence.
# Persistence is meaningless without a window: one night tells you nothing about
# whether a source is permanent.
CONTEXT_WINDOW_DAYS = 90
CONTEXT_RADIUS_DEG = 0.05  # ~5.5 km; comfortably wider than the 500 m site radius


class ThermalClassifierService:
    """Loads the trained bundle and scores detections with abstention."""

    def __init__(self, artifact_path: Optional[str] = None):
        self.artifact_path = artifact_path or DEFAULT_ARTIFACT
        self._bundle: Optional[Dict[str, Any]] = None
        self._load_error: Optional[str] = None

    @property
    def is_ready(self) -> bool:
        return self._bundle is not None

    def load(self) -> bool:
        """Load the model bundle. Returns False rather than raising.

        A missing artifact must not silently trigger training on demo data inside a
        request handler, which is what the previous loader did - a production endpoint
        would fit a model to simulated data on its first call and then serve it.
        """
        if self._bundle is not None:
            return True
        if not os.path.exists(self.artifact_path):
            self._load_error = (
                f"No model artifact at {self.artifact_path}. Run: "
                "python scripts/build_dataset.py --source sim"
            )
            logger.error(self._load_error)
            return False
        try:
            self._bundle = joblib.load(self.artifact_path)
            logger.info(
                "Loaded classifier: %d features, classes=%s",
                len(self._bundle.get("features", [])),
                self._bundle.get("classes"),
            )
            return True
        except Exception as exc:
            self._load_error = f"Failed to load {self.artifact_path}: {exc}"
            logger.exception(self._load_error)
            return False

    def status(self) -> Dict[str, Any]:
        return {
            "ready": self.is_ready,
            "artifact_path": self.artifact_path,
            "error": self._load_error,
            "classes": (self._bundle or {}).get("classes"),
            "abstain_threshold": (self._bundle or {}).get("abstain_threshold"),
        }

    def classify_detections(
        self,
        detections: List[Dict[str, Any]],
        facilities: Optional[List[Dict[str, Any]]] = None,
        target_index: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Score detections, computing site features across the whole batch.

        `detections` should include the target detection AND its spatial-temporal
        neighbours, because persistence and site baselines are computed from them.
        Pass `target_index` to get back only that detection's result.
        """
        if not self.load():
            raise RuntimeError(self._load_error or "classifier unavailable")

        if not detections:
            return []

        from ml.features.site_features import build_feature_frame
        from ml.training.train_pipeline import predict_with_abstention

        df = pd.DataFrame(detections)
        feats = build_feature_frame(df, facilities=facilities or [])
        results = predict_with_abstention(self._bundle, feats)

        from ml.features.site_features import SITE_FEATURE_COLUMNS

        for res, (_, row) in zip(results, feats.iterrows()):
            res["evidence"] = self._explain(row, res["predicted_class"])
            res["site_id"] = int(row.get("site_id", -1))
            res["persistence_ratio"] = float(row.get("persistence_ratio", 0.0) or 0.0)
            res["features"] = {
                col: (None if pd.isna(row.get(col)) else float(row.get(col)))
                for col in SITE_FEATURE_COLUMNS
                if col in row.index
            }

        if target_index is not None:
            return [results[target_index]]
        return results

    def _explain(self, row: pd.Series, predicted: str) -> Dict[str, Any]:
        """Build human-readable evidence from values that were actually measured.

        Every bullet cites a real quantity. Nothing is emitted for a feature whose
        source was unavailable.
        """
        bullets: List[str] = []

        persistence = row.get("persistence_ratio")
        n_days = row.get("site_n_days")
        span = row.get("site_lifetime_days")
        if persistence is not None and span and span > 1:
            bullets.append(
                f"Active on {int(n_days or 0)} of {int(span)} observed days "
                f"({float(persistence) * 100:.0f}% persistence)"
            )

        dist = row.get("dist_industrial_km")
        if dist is not None and float(dist) < 50.0:
            bullets.append(f"{float(dist) * 1000:.0f} m from mapped industrial infrastructure (OSM)")

        dmine = row.get("dist_mine_km")
        if dmine is not None and float(dmine) <= 2.0:
            bullets.append(f"{float(dmine) * 1000:.0f} m from a mapped quarry or mine")

        dland = row.get("dist_landfill_km")
        if dland is not None and float(dland) <= 2.0:
            bullets.append(f"{float(dland) * 1000:.0f} m from a mapped landfill")

        delta = row.get("brightness_delta")
        if delta is not None and float(delta) >= 25.0:
            bullets.append(
                f"I4-I5 separation {float(delta):.1f} K - sub-pixel source far hotter "
                "than a spreading vegetation fire"
            )

        z = row.get("frp_zscore_at_site")
        frp = row.get("frp")
        base = row.get("site_frp_median")
        if z is not None and float(z) >= 4.0 and base:
            bullets.append(
                f"FRP {float(frp):.0f} MW against this site's own baseline of "
                f"{float(base):.0f} MW ({float(z):.0f} sigma above normal operation)"
            )

        drift = row.get("centroid_drift_km")
        if drift is not None and float(drift) <= 0.2:
            bullets.append(f"Source stationary to within {float(drift) * 1000:.0f} m across overpasses")

        return {
            "factors": bullets[:5],
            "primary": bullets[0] if bullets else "Insufficient measured evidence",
            "predicted_class": predicted,
        }

    def classify_hotspot_legacy(
        self,
        hotspot_record: Dict[str, Any],
        neighbour_records: Optional[List[Dict[str, Any]]] = None,
        facilities: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Score one detection and return the shape the older call sites expect.

        `intelligence.py` and `predictions.py` were written against
        TwoStageThermalClassifier.predict_detailed(), which returned
        predicted_class / confidence_score / class_probabilities /
        feature_importances / explanation. Rather than rewrite both pipelines around
        the new return shape, this adapter maps the site-level classifier onto that
        contract so the rewire is a two-line change at each call site.

        Neighbours matter. Persistence and a site's own FRP baseline cannot be
        computed from a single detection, so `neighbour_records` should carry the
        surrounding spatial-temporal window. With none supplied the detection still
        classifies, but as a site of size one - which is legitimately what an
        isolated one-off fire looks like.

        Never raises. A classification failure returns an explicit abstention rather
        than a guess, because a silent fallback to a made-up class is exactly the
        behaviour this rewrite exists to remove.
        """
        records = [hotspot_record] + list(neighbour_records or [])
        try:
            scored = self.classify_detections(
                records, facilities=facilities or [], target_index=0
            )[0]
        except Exception as exc:  # noqa: BLE001 - must degrade, never 500 the caller
            logger.warning("Classification unavailable (%s); abstaining", str(exc)[:120])
            return {
                "predicted_class": "uncertain",
                "confidence_score": None,
                "class_probabilities": None,
                "feature_importances": {},
                "explanation": {
                    "primary_driver": "Classifier unavailable",
                    "top_factors": [str(exc)[:160]],
                    "method": "abstention",
                    "requires_human_review": True,
                },
            }

        evidence = scored.get("evidence", {}) or {}
        return {
            "predicted_class": scored["predicted_class"],
            "confidence_score": scored["confidence"],
            "class_probabilities": scored["class_probabilities"],
            # The deployed bundle publishes no global importance vector. Returning an
            # empty map is honest; the per-detection evidence below is what actually
            # explains this prediction.
            "feature_importances": {},
            "explanation": {
                "primary_driver": evidence.get("primary", "Insufficient measured evidence"),
                "top_factors": evidence.get("factors", []),
                "method": "site-level classification with abstention",
                "requires_human_review": scored.get("requires_human_review", False),
                "site_id": scored.get("site_id"),
                "persistence_ratio": scored.get("persistence_ratio"),
            },
        }

    @staticmethod
    def context_window(acq_date: datetime.date) -> tuple:
        """Date range to pull neighbouring detections for persistence computation."""
        return (acq_date - datetime.timedelta(days=CONTEXT_WINDOW_DAYS), acq_date)


# Module-level singleton reused across requests; loading the bundle per request would
# dominate latency.
classifier_service = ThermalClassifierService()
