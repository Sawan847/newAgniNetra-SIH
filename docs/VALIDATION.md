# Validation evidence - 11 September 2026

- Backend and ML suite: **63 passed**, 175.27 seconds. Includes API workflows, CSV deduplication and provenance, probability normalization, prior-day features, geometry conversion, missing-model behavior, worker-thread SSE delivery and report data integrity.
- Frontend: **8 tests passed** across four test files. TypeScript and the Vite production build passed. The bundle still produces Vite's large-chunk warning (approximately 1.49 MB JavaScript before gzip); performance tuning remains useful.
- Alembic: all three migrations rendered successfully to PostgreSQL SQL (`data/processed/schema_migrations.sql`). No live PostGIS server was available here. A CI PostGIS migration step is configured but has not been executed remotely in this session.
- NASA/OSM: public FIRMS CSV actually downloaded; 2,782 selected observations, 10 OSM facilities. Raw observations, download hash and acquisition dates are retained in `data/raw/observed/`.
- PDF: report generated from an actual NASA observation; missing model and satellite context remain unavailable. Rendered using Poppler for visual inspection.

**Browser smoke passed:** header snapshot link, 2,782 observations, 10 facility markers, cluster/heatmap toggles, acquisition timeline and honest missing-model metrics; no uncaught page errors. API requests deliberately return 503 and basemap tiles are fixtures, so this verifies snapshot mode without claiming a live database or live basemap check.

Tests use SQLite and mocks for portions of the backend. They do not prove PostGIS spatial behavior, live FIRMS key-based access, authenticated Earth Engine sampling, deployment health, scientific accuracy, event-delivery latency or security compliance. No model trained on independently verified incident labels is included.

## Observatory visual refresh

The shared interface now uses a charcoal/ember/cyan theme, decorative orbital SVG, updated metric icons, responsive controls and reduced-motion styling. Production build passed. Browser checks at 1440 x 1080 and 390 x 844 verified snapshot loading, rendered map initialization, heatmap/clusters, replay, collapsing navigation and mobile navigation. No uncaught page errors or horizontal overflow were observed. Browser-only fixture tiles avoid automated requests to OSM community servers; they are not application basemap data.
