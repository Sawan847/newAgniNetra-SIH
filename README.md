# AgniNetra AI — SIH26162

A geospatial prototype for **AI-Based Detection and Classification of Industrial Fires and Persistent Thermal Sources Using NASA FIRMS, OSM & Satellite Data**, proposed for NTRO / Disaster Management.

**Current status:** working application code, observed NASA/OSM snapshot, data imports, geospatial enrichment, analyst review and a supervised training pipeline. Real incident-classification accuracy has **not** been established. Missing evidence stays missing; synthetic models are refused by operational inference.

## Fastest working setup — no Docker, no database server, no API key

Five commands from a clean clone to a dashboard with classified data in it. This is
the path to use if anything else in this README has failed you.

**1. Configuration.** `.env.example` defaults to SQLite, so no database server is
needed.

```powershell
Copy-Item .env.example .env
```

**2. Python dependencies.**

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: -r backend/requirements.txt
```

**3. Build the dataset and train.** This step is not optional — without it there is
no model artifact and no classified data, and the dashboard will correctly render
empty panels.

```powershell
.\.venv\Scripts\python.exe scripts/build_dataset.py --source sim
```

Writes `ml/artifacts/thermal_classifier.joblib` and `ml/artifacts/model_card.json`.
`--source sim` uses the offline detection simulator, so no NASA key is required.

**4. Load it into the database.**

```powershell
.\.venv\Scripts\python.exe scripts/seed_from_pipeline.py --reset --limit 12000
```

**5. Run both servers**, in two terminals, from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
```

```powershell
npm install --prefix frontend
npm run dev --prefix frontend
```

Open **http://localhost:5173**. API docs at **http://localhost:8000/docs**.

### With real NASA data

Get a free instant key at
[firms.modaps.eosdis.nasa.gov/api/map_key](https://firms.modaps.eosdis.nasa.gov/api/map_key/),
put it in `.env` as `FIRMS_MAP_KEY`, then replace step 3 with:

```powershell
.\.venv\Scripts\python.exe scripts/build_dataset.py --source firms --sources VIIRS_SNPP_SP --bbox 68,18,88,33 --start 2026-03-05 --days 50
.\.venv\Scripts\python.exe scripts/seed_from_pipeline.py --reset --from-processed data/processed/labelled_detections.csv --limit 25000
```

`VIIRS_SNPP_SP` is the standard-processing archive, which reaches back to 2012. The
near-real-time products retain only about two months, and India's fire regime is
strongly seasonal — paddy residue burns Oct–Nov, wheat residue Apr–May, forest fires
Feb–Jun — so a live NRT pull landing in the monsoon contains almost no agricultural
or vegetation fire to classify. The March–April window above covers forest fire
season and the start of rabi stubble burning.

### Troubleshooting

| Symptom | Cause |
|---|---|
| Every panel reads 0 | Step 3 and 4 were skipped — there is no model and no data |
| `Model Intelligence` says "No model trained" | Step 3 was skipped |
| `ModuleNotFoundError` on startup | Step 2 incomplete; run it from the project root |
| pip fails building `pydantic-core` | Very recent Python; the `--only-binary=:all:` flag above avoids it |
| Dashboard looks stale after a rebuild | Hard-refresh the browser (Ctrl+Shift+R) |

---

## Try the observed-data map now

The repository includes a dated snapshot of **2,782 NASA FIRMS VIIRS observations (3–10 September 2026)** in an India bounding box, plus **10 OSM facilities around Jamnagar**. A bounding box also includes portions of neighbouring countries; these are not an India administrative-boundary clip. These are observations, not verified industrial-fire labels.

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and select **Explore NASA + OSM snapshot**. No database or NASA key is required for this snapshot. Basemap tiles require internet. Database status can show unavailable until the backend is running. Snapshot filters and saved actions require switching to database mode.

Snapshot data: `frontend/public/data/observations.json`. Raw download and provenance: `data/raw/observed/`. The manifest records acquisition dates, download URL, retrieval timestamp, SHA-256, dataset counts and attribution. Refresh it from the project root:

```powershell
python scripts/download_observations.py
```

## Run the complete stack

Install Docker Desktop, then from the project root:

```powershell
Copy-Item .env.example .env
# Edit .env: choose database/secret values and optionally add FIRMS_MAP_KEY.
docker compose up --build -d
```

Frontend: http://localhost:5173 · API: http://localhost:8000/docs

The backend container includes the `ml` package and applies Alembic migrations before starting. Compose forwards NASA/OSM/Earth Engine settings and connects Vite to the backend container.

For local Python development, start the PostGIS service with `docker compose up -d db`, then:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
cd backend
..\.venv\Scripts\python.exe -m alembic upgrade head
cd ..
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

Run the backend from the project root so Python can import both `app` and `ml`. Configuration reads the project `.env` consistently.

## Import the requested datasets

1. In **System Health**, import OSM facilities for a small region. The default region surrounds Jamnagar; Overpass imports are capped at 4 square degrees per request. Closed OSM way footprints are retained. Complex relations remain facility centre points until polygon topology is assembled.
2. Import a downloaded **NASA FIRMS VIIRS CSV**, or set `FIRMS_MAP_KEY` and use the FIRMS acquisition-date form. API requests use VIIRS SNPP, NOAA-20 and NOAA-21, with at most five days per source/request. Repeated CSV imports do not create duplicate detections or predictions.
3. Set `EE_PROJECT_ID` and authenticate Earth Engine, or provide `EE_SERVICE_ACCOUNT` and `EE_PRIVATE_KEY`. Install dependencies from `backend/requirements.txt`. The service samples **ESA WorldCover 2021 v200** and cloud-masked **Sentinel-2 SR Harmonized** pre-event imagery.
4. Use **Incident Investigation** to compute features and review evidence. Distances are kilometres; risk scoring converts them to metres. Centre proximity does not prove polygon containment. Persistence counts distinct prior acquisition days within 1 km, not repeated passes on one day.

Missing imagery, land cover and historical FRP baselines remain null. Detection-time inference does not use future Sentinel-2 scenes. Retrospective before/after delta-NBR remains a separate, unimplemented analysis workflow; it is not fabricated.

## Train with defensible labels

NASA FIRMS detects thermal anomalies; its confidence field is not an industrial-fire class label. OSM proximity and WorldCover land cover are contextual evidence, not independent accident confirmation.

The five known classes are `accidental_industrial_fire`, `persistent_industrial_source`, `forest_or_natural_fire`, `agricultural_burning`, and `mining_or_other`. `uncertain` is an abstention decision. Unknown labels are not trained as industrial fires.

Collect reviewed incidents and controls with dated evidence (incident records, facility operating information, independently reviewed imagery). Record reviewer identity and an evidence reference through Analyst Labelling. Then:

```powershell
python scripts/export_training.py data/processed/verified_features.csv
# Audit the CSV: keep observations from each facility/incident in one spatial_group.
python scripts/train_verified.py data/processed/verified_features.csv
```

The training command requires schema-v2 observed features, five known classes, reviewer/evidence metadata, at least 100 observations and at least three independent groups. These are software minimums, not proof of sufficient scientific validation. It selects an algorithm using spatial validation and reports chronological holdout metrics. The model card records provenance and the input-file hash. Restart the backend after replacing a model.

Without a provenance-checked artifact, inference returns **Uncertain**, with no invented confidence or automatic incident alert. Model Intelligence shows **Not evaluated** instead of hardcoded scores. Risk scores are unvalidated analyst-triage heuristics, not accident probabilities or emergency-dispatch decisions.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest -q
cd frontend
npm run typecheck
npm run build
npm test
```

Tests cover API workflows, duplicate imports, missing-data behavior, probability normalization, chronology, geometry conversion, model fitting and frontend components. SQLite tests do not replace live PostGIS integration testing. Browser verification can use `scripts/smoke_frontend.cjs` with Playwright and Edge available. It stubs API failures and basemap tiles to exercise snapshot mode without querying community tiles from a headless browser. See [validation evidence](docs/VALIDATION.md).

An example report can be regenerated from the raw NASA CSV with `python scripts/render_sample_report.py`; its missing classification and satellite context remain explicitly unavailable.

## SIH submission preparation

See [the SIH readiness and demonstration guide](docs/SIH26162_READINESS.md) for requirement mapping, actual fixes, demonstration sequence and outstanding validation.

This is a hackathon prototype, not a production emergency system. Before public deployment, enforce authentication across mutation endpoints, replace demo account defaults, add operational monitoring, verify PostGIS migrations on a real database and validate incident labels on independent events/regions. Do not present gas-leak/explosion confirmation, calibrated real-world accuracy or emergency-service dispatch as implemented capabilities.

## Official data references

- [NASA FIRMS map](https://firms.modaps.eosdis.nasa.gov/map/) — the problem statement's `modap` hostname should be `modaps`.
- [FIRMS Area API](https://firms.modaps.eosdis.nasa.gov/api/area/) and [free MAP_KEY registration](https://firms.modaps.eosdis.nasa.gov/api/map_key/).
- [NASA recent fire downloads](https://firms.modaps.eosdis.nasa.gov/active_fire/) and [archive download](https://firms.modaps.eosdis.nasa.gov/download/).
- [OSM Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API); © OpenStreetMap contributors, ODbL.
- [ESA WorldCover v200 catalog](https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200), 2021, 10 m, CC BY 4.0.
- [Sentinel-2 SR Harmonized catalog](https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED).

We acknowledge NASA FIRMS / LANCE and the OpenStreetMap contributors. No affiliation with NTRO is implied.
