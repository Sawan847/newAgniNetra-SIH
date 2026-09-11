import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import settings
from app.middleware.error_handler import register_error_handlers
from app.middleware.logging_middleware import LoggingMiddleware
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for background schedules and startup seeding."""
    from app.services.events import broadcaster
    broadcaster.bind(asyncio.get_running_loop())
    if settings.environment == "development":
        try:
            from app.database import SessionLocal
            from app.services.auth import seed_default_admin
            with SessionLocal() as db:
                seed_default_admin(db)
        except Exception as exc:
            logger.warning("Default admin startup seeding deferred: %s", exc)

    scheduler_task = None
    if settings.enable_scheduled_ingestion and settings.effective_firms_map_key:
        async def _scheduled_ingestion_loop():
            from app.database import SessionLocal
            from app.services.ingestion import IngestionService
            import datetime
            def ingest_once():
                # Create, use and close the SQLAlchemy session in the same worker.
                with SessionLocal() as db:
                    today = datetime.datetime.now(datetime.timezone.utc).date()
                    return IngestionService(db).run_firms_ingestion(
                        bbox=(68.0, 8.0, 97.0, 37.0), start_date=today)

            while True:
                await asyncio.sleep(settings.ingestion_interval_minutes * 60)
                try:
                    await asyncio.to_thread(ingest_once)
                except Exception as exc:
                    logger.warning("Scheduled ingestion run error: %s", exc)

        scheduler_task = asyncio.create_task(_scheduled_ingestion_loop())
        logger.info("Automated FIRMS ingestion scheduler activated (interval=%dm)", settings.ingestion_interval_minutes)

    try:
        yield
    finally:
        if scheduler_task:
            scheduler_task.cancel()
            with suppress(asyncio.CancelledError):
                await scheduler_task
        broadcaster.bind(None)


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    setup_logging()

    application = FastAPI(
        title="AgniNetra AI",
        description="Industrial Thermal Intelligence and Fire Classification Platform",
        version="0.1.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request logging
    application.add_middleware(LoggingMiddleware)

    # Error handlers
    register_error_handlers(application)

    # Friendly root route: opening the backend in a browser should confirm
    # that the API is running instead of returning a confusing 404.
    @application.get("/", include_in_schema=False)
    def root_status():
        return {
            "name": "AgniNetra AI API",
            "status": "running",
            "api_base": "/api/v1",
            "health": "/api/v1/health",
            "docs": "/docs" if settings.is_development else None,
        }

    # Routes
    application.include_router(api_router)

    return application


app = create_app()
