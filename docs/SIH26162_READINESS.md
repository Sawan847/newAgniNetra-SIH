# SIH26162 — implementation and demonstration guide

## Requirement mapping

| SIH requirement | Implementation | Current evidence / remaining work |
|---|---|---|
| Integrate NASA FIRMS thermal anomalies | VIIRS Area API batching, CSV imports, deterministic event IDs, acquisition times and original rows | Real public snapshot downloaded; key-based Area API requires the team's MAP_KEY |
| Integrate industrial infrastructure | Regional OSM Overpass import with tags, facility centres and closed-way polygons | 10 observed facility records included for Jamnagar; OSM is incomplete and public servers may time out |
| Segregate industrial and natural sources | Two-stage supervised classifier: macro domain then industrial persistent/accidental | Training and inference code tested; independent verified incident labels and real-world evaluation remain required |
| Monitor persistent sources | Distinct prior acquisition days within 1 km, 7/30/90-day counts, same-sensor FRP history | Use a sufficiently long acquisition archive; lack of detections is not proof of inactivity |
| Integrate land cover and satellite imagery | ESA WorldCover 2021 v200 sampling; Sentinel-2 SR SCL-masked pre-event indices | Earth Engine account/project required; live sampling not verified in this environment |
| GIS storage and output overlays | PostGIS models/migrations, GeoJSON APIs, MapLibre detections, facility overlays, heatmap and clusters | PostgreSQL SQL migration generation checked; live database/Compose startup requires Docker/PostGIS |
| Review and explain decisions | Features/provenance, uncertainty, analyst labels and local alert queue | Human verification remains essential; no incident confirmation from FRP alone |

## Code issues corrected

- Frontend build errors from mismatched demo types, obsolete category names and missing imports.
- Invented satellite measurements and invented default land-cover/land-use distances.
- Runtime training on synthetic labels and hardcoded model-accuracy/confusion-matrix displays.
- Uncertain samples being mapped to industrial training labels and double-counted probability mass.
- Future and duplicate-day observations affecting recurrence; current FRP being used as its own historical baseline.
- PostGIS binary coordinates being treated as text and replaced with made-up facility locations.
- Proximity being called containment without a polygon, and kilometre distances being fed into metre risk thresholds.
- Missing OSM import path and nonfunctional map facility/clustering controls.
- Invalid FIRMS errors appearing as empty successful data, missing input validation and potentially exposed API keys in HTTP logs/errors.
- Repeated imports rerunning predictions for already-existing detections.
- Historical prediction joins duplicating/filtering hotspots by obsolete classes.
- Docker backend missing the ML package, missing alert/zone migrations and container-to-container API proxy configuration.

- Report exports inventing model versions, scores or cloud conditions; reports now preserve missing data and saved evidence.
- Named SSE events not reaching clients from database workers, and readiness checks returning success when the database is unavailable.
- Inert demo/timeline controls, unsupported government branding and inaccurate deployment/model documentation.

## Suggested five-minute demonstration

1. Open the operations page and choose **Explore NASA + OSM snapshot**. State its actual acquisition dates and explain that gray points are unclassified observations. Distinguish FIRMS FRP (MW) from ground temperature or fire size.
2. Zoom to Jamnagar. Show cyan OSM facility markers, click a facility, toggle the heatmap and clusters, and select a thermal observation. Explain why a routine industrial flare can appear in FIRMS.
3. In the full stack, open **System Health**, import a small OSM region and a NASA CSV. Repeat the CSV import to demonstrate deduplication.
4. Investigate an observation. Show prior-day persistence, same-sensor historical FRP, known/missing imagery and facility distance. Explain why missing evidence leads to uncertainty.
5. Show **Analyst Labelling** and **Model Intelligence**. Before training, demonstrate truthful “Not evaluated” states. After gathering independently reviewed labels, show the resulting model card, class-wise precision/recall, confusion matrix and chronological holdout results.

## What makes the proposal defensible

Use independently verified accidental-industrial-fire incidents, persistent operational sources, agricultural burns, natural fires and mining-associated thermal sources. Keep all passes from a single facility or incident in the same group. Balance sensor, region and season coverage; document label ambiguity. Reserve unseen regions/events and later dates before model tuning. Report both false alerts and missed industrial incidents; show abstention coverage rather than hiding uncertain cases.

A 2021 WorldCover class is historical context, not current land use. Built-up land does not prove an industrial site; bare ground does not prove mining. Optical burn indices do not directly measure industrial heat. Satellite cloud cover, revisit timing, pixel footprint, geolocation uncertainty and missing OSM tags affect interpretation. An industrial accident needs corroborating evidence.

## Before claiming completion of the AI deliverable

- Configure and test the team's NASA MAP_KEY and Earth Engine project.
- Start PostGIS and exercise the full CSV → storage → feature extraction → prediction → GeoJSON workflow on real observations.
- Gather a reviewed reference dataset with incident/facility sources, then audit spatial groups and acquisition-time cutoffs.
- Train with `scripts/train_verified.py`; inspect per-class holdout results and false-alert rates before activating the artifact.
- Add a separately labelled retrospective Sentinel-2 before/after comparison if it is part of the final presentation. Delta-NBR is presently unavailable in live inference.
- Confirm persistence against facility operating history; observed recurrence alone cannot certify normal operation.

The live model is intentionally untrained until these inputs exist. The downloaded snapshot and passing software tests do not establish real-world classification accuracy.
