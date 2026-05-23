from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.core.config import Settings
from app.db.session import Base, engine
from app.models import User, UserRole


def run_startup_self_check(settings: Settings) -> None:
    if settings.env == "demo" and settings.llm_required and not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when ENV=demo and LLM_REQUIRED=true")


def create_schema() -> None:
    Base.metadata.create_all(bind=engine)


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
