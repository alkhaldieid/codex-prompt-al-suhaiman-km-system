import logging

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.core.config import Settings
from app.db.session import Base, engine
from app.models import Document, SourceTrack, User, UserRole
from app.services.regulatory_seed import seed_regulatory_corpus
from app.services.migrations import apply_migrations

logger = logging.getLogger(__name__)


def run_startup_self_check(settings: Settings) -> None:
    if settings.llm_required and not settings.openai_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is required when LLM_REQUIRED=true. "
            "Set it in .env or run with the dev-no-llm profile."
        )


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)
    apply_migrations()


def seed_demo_users(db: Session) -> None:
    users = [
        ("lawyer.a@demo.suhaiman.sa", "المحامي أ", UserRole.lawyer),
        ("lawyer.b@demo.suhaiman.sa", "المحامي ب", UserRole.lawyer),
        ("reviewer@demo.suhaiman.sa", "المراجع", UserRole.reviewer),
        ("admin@demo.suhaiman.sa", "مدير النظام", UserRole.admin),
    ]
    for email, name, role in users:
        exists = db.scalar(select(User).where(User.email == email))
        if exists:
            continue
        db.add(
            User(
                email=email,
                password_hash=hash_password("DemoPass123!"),
                display_name_ar=name,
                display_name_en=email.split("@")[0],
                role=role,
            )
        )
    db.commit()


def purge_placeholder_seed(db: Session) -> None:
    """Remove the old placeholder regulatory documents (the descriptive
    paragraphs about each regulator), identified by their UUID range
    111…1101–111…1110. Idempotent — no-op once real corpus is in place.
    """
    purged = db.execute(
        delete(Document).where(
            Document.storage_key.like("seed/11111111%"),
            Document.source_track == SourceTrack.track1_external,
        )
    )
    if purged.rowcount:
        logger.info("purged %d placeholder regulator-description docs", purged.rowcount)
        db.commit()


def seed_startup_data(db: Session) -> None:
    seed_demo_users(db)
    purge_placeholder_seed(db)
    seed_regulatory_corpus(db)
