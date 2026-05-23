from typing import Annotated
from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.security import decode_token, role_allows
from app.core.errors import AppProblem
from app.db.session import get_db
from app.models.user import User, UserRole

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if credentials is None:
        raise AppProblem(
            status=401,
            title="يلزم تسجيل الدخول",
            detail="يرجى تسجيل الدخول للمتابعة",
            type_="https://ethka.dev/errors/auth-required",
        )
    try:
        payload = decode_token(credentials.credentials)
    except JWTError as exc:
        raise AppProblem(
            status=401,
            title="جلسة غير صالحة",
            detail="انتهت صلاحية الجلسة أو أن رمز الدخول غير صحيح",
            type_="https://ethka.dev/errors/invalid-token",
        ) from exc

    user = db.get(User, UUID(payload["sub"]))
    if user is None:
        raise AppProblem(
            status=401,
            title="المستخدم غير موجود",
            detail="تعذر العثور على المستخدم المرتبط بهذه الجلسة",
            type_="https://ethka.dev/errors/user-not-found",
        )
    return user


def require_role(required: UserRole):
    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not role_allows(user.role, required):
            raise AppProblem(
                status=403,
                title="صلاحيات غير كافية",
                detail="لا تملك الصلاحية المطلوبة لتنفيذ هذا الإجراء",
                type_="https://ethka.dev/errors/forbidden",
            )
        return user

    return dependency
