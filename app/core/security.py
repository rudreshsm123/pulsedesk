import uuid
from datetime import UTC, datetime, timedelta
from enum import StrEnum

import bcrypt
import jwt

from app.core.config import get_settings

settings = get_settings()


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def _create_token(subject: str, role: str, token_type: TokenType, expires_delta: timedelta) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "type": token_type.value,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id,
        role,
        TokenType.ACCESS,
        timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(user_id: str, role: str) -> str:
    return _create_token(
        user_id,
        role,
        TokenType.REFRESH,
        timedelta(days=settings.refresh_token_expire_days),
    )


class InvalidTokenError(Exception):
    pass


def decode_token(token: str, expected_type: TokenType) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc

    if payload.get("type") != expected_type.value:
        raise InvalidTokenError(f"expected a {expected_type.value} token")

    return payload
