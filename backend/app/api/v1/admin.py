"""Admin endpoints: connector controls + sanity checks.

Only the manual MoJ trigger lives here today. Future admin work
(review queue, contributor promotion, kill-switch toggles) lands here.
Endpoints are gated to admin role and (for the connector trigger) to
demo/dev env so we never let a partner accidentally trigger a sync
against prod from a demo button.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.connectors import moj
from app.core.config import get_settings
from app.core.errors import AppProblem
from app.db.session import get_db
from app.models import User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(user: User) -> None:
    if user.role != UserRole.admin:
        raise AppProblem(
            status=403,
            title="غير مصرّح",
            detail="يلزم دور المشرف",
            type_="https://ethka.dev/errors/forbidden",
        )


@router.post("/connectors/moj/sync")
async def trigger_moj_sync(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Manually trigger a MoJ resync. Admin-only. Demo/dev env only."""
    _require_admin(user)
    settings = get_settings()
    if settings.env not in {"demo", "dev"}:
        raise AppProblem(
            status=403,
            title="معطّل في البيئة الحالية",
            detail="مفتاح المزامنة اليدوية متاح في بيئتي العرض والتطوير فقط",
            type_="https://ethka.dev/errors/disabled-in-env",
        )
    result = await moj.sync(db, max_pages=3)
    return {
        "items_seen": result.items_seen,
        "created": result.created,
        "updated": result.updated,
        "unchanged": result.unchanged,
        "skipped_empty": result.skipped_empty,
        "errors": result.errors[:10],
    }
