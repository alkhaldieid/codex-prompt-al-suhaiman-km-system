import asyncio

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import admin, auth, documents, health, search
from app.connectors import moj
from app.core.config import get_settings
from app.core.errors import AppProblem, problem_exception_handler
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.startup import create_schema, run_startup_self_check, seed_startup_data

configure_logging()
logger = structlog.get_logger()
settings = get_settings()

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_exception_handler(AppProblem, problem_exception_handler)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://frontend:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.api_v1_prefix)
app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(documents.router, prefix=settings.api_v1_prefix)
app.include_router(search.router, prefix=settings.api_v1_prefix)
app.include_router(admin.router, prefix=settings.api_v1_prefix)


SECONDS_PER_DAY = 24 * 60 * 60


async def _daily_moj_sync() -> None:
    """Background loop: re-run the MoJ sync once a day. Asyncio.create_task'd
    from the startup hook — no Celery / no APScheduler / no new container."""
    while True:
        await asyncio.sleep(SECONDS_PER_DAY)
        try:
            with SessionLocal() as db:
                result = await moj.sync(db, max_pages=3)
            logger.info(
                "daily_moj_sync_done",
                created=result.created,
                updated=result.updated,
                unchanged=result.unchanged,
                errors=len(result.errors),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("daily_moj_sync_failed", error=str(exc))


@app.on_event("startup")
def startup() -> None:
    run_startup_self_check(settings)
    create_schema()
    with SessionLocal() as db:
        seed_startup_data(db)
    logger.info("service_started", service="backend", env=settings.env)


@app.on_event("startup")
async def schedule_daily() -> None:
    # Run an immediate MoJ sync now that we have an async context.
    # asyncio.run() can't nest into FastAPI's own loop, which is why the
    # seed shim deferred to us.
    try:
        with SessionLocal() as db:
            result = await moj.sync(db, max_pages=3)
        logger.info(
            "boot_moj_sync_done",
            seen=result.items_seen,
            created=result.created,
            updated=result.updated,
            unchanged=result.unchanged,
            empty=result.skipped_empty,
            errors=len(result.errors),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("boot_moj_sync_failed", error=str(exc))
    asyncio.create_task(_daily_moj_sync())
