from fastapi import APIRouter, Depends, Query

from app.auth.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/search", tags=["search"])


@router.get("")
def search(q: str = Query(min_length=1), _: User = Depends(get_current_user)) -> dict:
    return {
        "query": q,
        "total": 0,
        "took_ms": 0,
        "results": [],
        "message": "لم يتم تفعيل الفهرس بعد. سيكتمل ذلك في أسبوع البحث والفهرسة.",
    }
