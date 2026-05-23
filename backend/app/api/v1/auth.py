from uuid import UUID

from fastapi import APIRouter, Depends
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.security import create_token, decode_token, verify_password
from app.core.errors import AppProblem
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPair, UserProfile

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenPair:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AppProblem(
            status=401,
            title="بيانات الدخول غير صحيحة",
            detail="البريد الإلكتروني أو كلمة المرور غير صحيحة",
            type_="https://ethka.dev/errors/invalid-credentials",
        )
    return TokenPair(
        access_token=create_token(user, token_type="access"),
        refresh_token=create_token(user, token_type="refresh"),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token)
    except JWTError as exc:
        raise AppProblem(
            status=401,
            title="جلسة غير صالحة",
            detail="رمز تحديث الجلسة غير صالح أو منتهي الصلاحية",
            type_="https://ethka.dev/errors/invalid-refresh-token",
        ) from exc

    if claims.get("typ") != "refresh":
        raise AppProblem(
            status=401,
            title="نوع الرمز غير صحيح",
            detail="يرجى استخدام رمز تحديث صالح",
            type_="https://ethka.dev/errors/wrong-token-type",
        )

    user = db.get(User, UUID(claims["sub"]))
    if user is None:
        raise AppProblem(
            status=401,
            title="المستخدم غير موجود",
            detail="تعذر العثور على المستخدم المرتبط بهذه الجلسة",
            type_="https://ethka.dev/errors/user-not-found",
        )

    return TokenPair(
        access_token=create_token(user, token_type="access"),
        refresh_token=create_token(user, token_type="refresh"),
    )


@router.get("/me", response_model=UserProfile)
def me(user: User = Depends(get_current_user)) -> UserProfile:
    return UserProfile(
        user_id=str(user.user_id),
        email=user.email,
        display_name_ar=user.display_name_ar,
        role=user.role.value,
    )
