# AgniNetra model card - implementation status

Status: **no validated incident classifier released**. This document describes the supervised pipeline, not a trained model with demonstrated field accuracy. Any earlier example accuracy, F1, calibration or feature-importance numbers are withdrawn because they were not supported by a verified evaluation dataset.

## Intended task

SIH26162: distinguish accidental industrial fires, persistent industrial sources, forest/natural fires, agricultural burning and mining/other activity. The sixth displayed result, `uncertain`, is an abstention decision. NASA FIRMS confidence is detection quality, not a class label or the probability of an industrial accident.

## Data and features

The bundled snapshot has 2,782 observed FIRMS VIIRS detections dated 3-10 September 2026 in a regional bounding box and 10 OSM facilities around Jamnagar. It contains **no verified incident labels** and is not an accuracy benchmark. Provenance is in `data/raw/observed/manifest.json`.

The schema-v2 model interface defines 37 columns in `ml/config.py`. Thermal values retain source units (FRP MW, brightness K); facility distances are km. Runtime extraction uses prior observations within 1 km, distinct prior acquisition days for persistence, same-satellite historical FRP, mapped facility footprints, and optional pre-event Sentinel-2/WorldCover samples. Missing imagery, land-cover distances, cluster direction/spread and retrospective delta-NBR remain unavailable where not implemented. Do not describe all 37 columns as measured evidence.

## Algorithm and evaluation protocol

Stage 1 predicts industrial versus the three non-industrial groups. Stage 2 separates persistent from accidental industrial events. Conditional probabilities are multiplied and normalized; predictions below the configured threshold abstain. Candidate tree models are selected using spatial validation, with a chronological holdout for reporting. Calibration is attempted only when class counts permit it. This is a software protocol, not evidence that calibration is accurate.

Use `scripts/export_training.py` and `scripts/train_verified.py` with independent analyst-reviewed labels, reviewer names and evidence references. Audit spatial groups so each incident/facility stays within a single evaluation partition; also audit repeated events across chronological boundaries. A minimum of 100 rows is a command precondition, not scientific sufficiency. Do not label accidents solely from FRP, OSM proximity or a model prediction.

## Release gate and metrics

Operational loading requires `training_source=analyst_verified_observations` and `feature_schema_version=2` in the generated artifact card. Metadata records provenance; it does not independently verify analyst judgments. Synthetic or unverified artifacts are refused. The API returns uncertain with null confidence when a qualifying model is absent.

Accuracy, precision/recall, macro-F1, confusion matrix, Brier score and field false-alert rate: **not established**. Report them only from held-out verified incidents with class supports, date/region splits, confidence intervals and a clear label audit. Generated training cards live in `ml/artifacts/model_card.json` after a successful run. Test-suite success measures software behavior only.

## Known limitations

Clouds, sensor footprints, overpass timing, stale land cover and incomplete OSM coverage affect evidence. Persistent flares and industrial accidents can overlap spatially. FIRMS alone cannot confirm gas leaks or explosions. Heuristic triage scores are not calibrated probabilities. This prototype requires analyst verification and independent regional validation before operational use.
