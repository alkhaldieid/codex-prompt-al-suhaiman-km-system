import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, documents, health, search
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


@app.on_event("startup")
def startup() -> None:
    run_startup_self_check(settings)
    create_schema()
    with SessionLocal() as db:
        seed_startup_data(db)
    logger.info("service_started", service="backend", env=settings.env)
