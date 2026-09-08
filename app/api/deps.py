import uuid
from collections.abc import Callable

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.enums import UserRole
from app.core.exceptions import InvalidCredentialsError, UnauthorizedActionError
from app.core.security import InvalidTokenError, TokenType, decode_token
from app.models.user import User
from app.repositories.user_repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    if token is None:
        raise InvalidCredentialsError("Missing bearer token")

    try:
        payload = decode_token(token, TokenType.ACCESS)
        user_id = uuid.UUID(payload["sub"])
    except (InvalidTokenError, ValueError) as exc:
        raise InvalidCredentialsError("Invalid or expired access token") from exc

    user = await UserRepository(session).get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsError("Invalid or expired access token")

    return user


def require_role(*allowed_roles: UserRole) -> Callable:
    async def checker(user: User = Depends(get_current_user)) -> User:
        if UserRole(user.role) not in allowed_roles:
            raise UnauthorizedActionError(
                f"Role '{user.role}' is not permitted to perform this action"
            )
        return user

    return checker
