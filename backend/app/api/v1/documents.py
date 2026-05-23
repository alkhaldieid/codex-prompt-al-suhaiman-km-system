from fastapi import APIRouter, Depends

from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/recent")
def recent_documents(_: User = Depends(get_current_user)) -> dict:
    return {
        "items": [],
        "message": "لا توجد مستندات حديثة بعد",
    }
