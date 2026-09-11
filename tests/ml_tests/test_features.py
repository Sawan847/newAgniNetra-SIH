"""Unit tests for ml.features.engineering.

This file previously imported compute_day_of_year, compute_persistence_score,
compute_cluster_spread_features and compute_historical_frp_baselines - none of which
exist in ml/features/engineering.py. The module was rewritten around
build_context_features / extract_firms_features and the tests were never updated, so
the whole ml_tests package failed at collection on a clean checkout and the suite
could not run at all.

Rewritten against the API the module actually exposes. Site-level persistence and
clustering, which the deleted tests were reaching for, now live in
ml/features/site_features.py and are covered by test_weak_supervision.py.
"""

from __future__ import annotations

import pytest

from ml.features.engineering import (
    build_context_features,
    extract_firms_features,
    extract_full_feature_vector,
    normalise_landcover,
)


class TestNormaliseLandcover:
    def test_none_is_handled(self):
        assert isinstance(normalise_landcover(None), str)

    def test_returns_a_string_for_arbitrary_input(self):
        for value in ("forest", "FOREST", "cropland", "built_up", "", "nonsense"):
            assert isinstance(normalise_landcover(value), str)

    def test_case_insensitive(self):
        assert normalise_landcover("Forest") == normalise_landcover("forest")


class TestBuildContextFeatures:
    def test_defaults_produce_a_feature_mapping(self):
        feats = build_context_features()
        assert isinstance(feats, dict)
        assert feats, "expected at least one feature"

    def test_all_values_are_numeric(self):
        feats = build_context_features(
            brightness=340.0, frp=25.0, confidence=80.0,
            industrial_distance_m=150.0,
        )
        for key, value in feats.items():
            assert isinstance(value, (int, float)), f"{key} is not numeric: {value!r}"

    def test_industrial_distance_changes_the_output(self):
        """Proximity to industry must actually move the feature vector.

        If it did not, the OSM layer would be contributing nothing to
        classification - which is the whole point of joining it.
        """
        near = build_context_features(brightness=340.0, frp=25.0, industrial_distance_m=100.0)
        far = build_context_features(brightness=340.0, frp=25.0, industrial_distance_m=50000.0)
        assert near != far


class TestExtractFirmsFeatures:
    def test_accepts_a_firms_shaped_record(self):
        feats = extract_firms_features({
            "latitude": 22.35, "longitude": 70.06,
            "bright_ti4": 361.2, "bright_ti5": 300.4,
            "frp": 47.3, "confidence": "n",
            "acq_date": "2026-04-15", "acq_time": "0214",
            "daynight": "N",
        })
        assert isinstance(feats, dict)

    def test_missing_fields_do_not_raise(self):
        assert isinstance(extract_firms_features({}), dict)


class TestExtractFullFeatureVector:
    def test_returns_numeric_mapping_with_no_input(self):
        feats = extract_full_feature_vector()
        assert isinstance(feats, dict)
        for key, value in feats.items():
            assert isinstance(value, (int, float)), f"{key} is not numeric: {value!r}"

    def test_no_nan_values_leak_into_the_vector(self):
        """A NaN reaching the model surfaces as a silent prediction error rather
        than an exception, so the feature builder must never emit one."""
        import math

        feats = extract_full_feature_vector()
        bad = [k for k, v in feats.items() if isinstance(v, float) and math.isnan(v)]
        assert bad == [], f"NaN in features: {bad}"
