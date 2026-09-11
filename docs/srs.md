# SIH26162 - requirements and acceptance plan

AgniNetra is a student prototype proposed for NTRO's industrial-fire and persistent-thermal-source problem. This document separates required behavior from current evidence; it does not claim government affiliation, standards compliance or completed operational validation.

| Requirement | Implemented behavior | Acceptance evidence / remaining work |
|---|---|---|
| Industrial versus natural-fire classification | Five known classes, two-stage model and uncertain abstention | Reviewed incident labels and held-out regional validation required |
| NASA FIRMS integration | Area API and CSV ingestion, source preservation and duplicate handling | Public VIIRS snapshot downloaded; credentialed API needs MAP_KEY |
| OSM infrastructure context | Regional Overpass imports, centers, closed-way footprints, distances and containment | Ten actual Jamnagar facilities bundled; relation topology and coverage audit remain |
| Satellite and land-cover context | Earth Engine WorldCover v200 and pre-event Sentinel-2 sampling | Credentials and live sampling verification remain; unavailable data stays null |
| Persistent-source evidence | Prior detections and distinct acquisition days; same-satellite FRP history | Acquire a longer historical baseline and validate facility operating behavior |
| GIS storage and overlays | SQLAlchemy/PostGIS schema, GeoJSON, MapLibre detections, facilities, heatmap and clusters | Live PostGIS migrations/spatial-query integration test remains |
| Analyst review | Feedback with evidence metadata; alert assignment/resolution and PDF export | Complete user identity enforcement and verify labels independently |
| Telemetry refresh | Named SSE invalidations after commits from database workers | Single process only; no durable delivery or latency guarantee |
| Reproducible validation | Regression tests, grouped model selection and chronological holdout | Report incident-level metrics and class supports from verified observations |

## Class taxonomy

`accidental_industrial_fire`, `persistent_industrial_source`, `forest_or_natural_fire`, `agricultural_burning`, `mining_or_other`. `uncertain` represents abstention, including missing model evidence. It is not a substitute ground-truth class.

## Acceptance constraints

- Missing or failed data requests must not report fabricated measurements or success counts.
- A nearby facility center must not be treated as proof of polygon containment.
- Detection-time features must not use future imagery or future thermal observations.
- Dates, units, dataset source and model provenance must be reviewable.
- Accuracy, response-time, availability and security targets are not achieved claims until independently measured.
- Risk scores support analyst triage only. The prototype must not claim confirmed gas leaks/explosions or emergency-service dispatch.

Detailed implementation status and the presentation sequence are in [SIH26162_READINESS.md](SIH26162_READINESS.md). Training limitations are in [model_card.md](model_card.md); deployment gaps are in [security.md](security.md).
