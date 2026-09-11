# Deployment and local operation

Start with the root [README](../README.md). All commands below are run from the repository root unless stated otherwise. Docker/PostGIS deployment has not been executed on the current machine because Docker is unavailable.

## Frontend with the bundled observations

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173/?snapshot=1`. This mode needs no database. The observation snapshot is local; basemap tiles need internet. It cannot save alerts, analyst labels or database enrichment.

## Development stack

```powershell
Copy-Item .env.example .env
# Edit .env, keeping DATABASE_URL consistent with the selected database values.
docker compose up --build -d
```

The frontend uses the Vite proxy at port 5173; the backend is at port 8000. Development API documentation is `/docs`. Health is `/api/v1/health`; readiness is `/api/v1/health/ready` and returns 503 if the database cannot be queried. System integration status is `/api/v1/system/status`.

For Python development, install `backend/requirements.txt` in a virtual environment, run Alembic from `backend`, then run `python -m uvicorn app.main:app --app-dir backend --reload --port 8000` from the project root. See the README for Windows commands.

## Local staging template

The filename `docker-compose.prod.yml` is retained for compatibility; this is a **staging template with incomplete access control**, not a hardened production deployment.

```powershell
# Configure unique POSTGRES_PASSWORD and SECRET_KEY in .env first.
docker compose -f docker-compose.prod.yml config
# Review the resulting configuration locally; it contains your secrets.
docker compose -f docker-compose.prod.yml up --build -d
```

The nginx frontend binds to `127.0.0.1:8080`; API requests are proxied internally. Database and backend ports are not published. The backend uses one worker because SSE subscriptions and optional scheduling are process-local. Data and ML paths are mounted, and Alembic runs before the backend starts. API Swagger UI is disabled in production environment mode.

Optional integration settings: `FIRMS_MAP_KEY`, `OSM_OVERPASS_URL`, `EE_PROJECT_ID`, `EE_SERVICE_ACCOUNT`, `EE_PRIVATE_KEY`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `ALERT_NOTIFICATION_EMAIL`. An Earth Engine private-key file path must refer to a file mounted inside the container; do not put it in the image. Automatic ingestion is disabled by default. Do not enable SMTP for a demonstration unless sending is intended.

The frontend accepts `VITE_API_BASE_URL` (server origin, without `/api/v1`) in `frontend/.env.local` at build time. Leave it empty for the nginx/Vite proxy. `VITE_BASEMAP_TILE_URL` and `VITE_BASEMAP_ATTRIBUTION` can select a permitted tile provider. For the default OSM standard tiles, retain visible attribution, browser caching and Referer headers; no bulk/offline tile download is provided. See the [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/).

## Remaining operational checks

Apply migrations against a live PostGIS database, verify imports and spatial predicates, confirm credentialed Earth Engine sampling, and exercise review/export workflows. A CI migration step is configured but has not been run remotely in this session. Complete the access-control work in [security.md](security.md) before exposing the service beyond the local machine. Preserve database volumes and verified model artifacts when upgrading; this guide does not require deleting them.
