from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt
from passlib.context import CryptContext

from app.core.config import get_settings
from app.models.user import User, UserRole

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ephemeral_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_ephemeral_private_pem = _ephemeral_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
).decode()
_ephemeral_public_pem = _ephemeral_key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
).decode()


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_token(user: User, *, token_type: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    payload = {
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "sub": str(user.user_id),
        "email": user.email,
        "role": user.role.value,
        "typ": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
    }
    return jwt.encode(payload, settings.jwt_private_key or _ephemeral_private_pem, algorithm="RS256")


def decode_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_public_key or _ephemeral_public_pem,
        algorithms=["RS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )


def role_allows(actual: UserRole, required: UserRole) -> bool:
    order = {
        UserRole.lawyer: 1,
        UserRole.reviewer: 2,
        UserRole.km_lead: 3,
        UserRole.admin: 4,
    }
    return order[actual] >= order[required]
