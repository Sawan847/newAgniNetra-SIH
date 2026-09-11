# Fixes applied

- Removed the committed NASA FIRMS MAP_KEY value from `.env.example`.
- Added a friendly backend `/` route so opening the API server no longer returns a confusing 404.
- Fixed `scripts/setup_dev.ps1` to use the same root `.venv` path as the README.
- Made Vite load environment values correctly for `API_PROXY_TARGET` / `VITE_API_BASE_URL`.
- Added `frontend/.env.example`, including the simple switch for a backend running on port 8001.
- Routed alert assignment/resolution and PDF report downloads through the configured API base instead of hard-coded relative `/api/v1` URLs.
- Removed generated/cache/dependency folders from the cleaned deliverable ZIP (`.venv`, `node_modules`, `.git`, build output, Python caches).

## Verification in this repair pass

- Python source compilation: passed.
- ML test suite: **13 passed**.
- Patched TypeScript/TSX files: syntax-transpilation check passed.
- Full frontend typecheck could not be rerun in this sandbox because npm dependency installation is network-blocked; the original project includes prior validation evidence showing the full frontend build/tests passed before these small integration edits.
- Full backend API suite could not be rerun here because this sandbox lacks project dependencies such as GeoAlchemy2; `backend/requirements.txt` already declares them.
