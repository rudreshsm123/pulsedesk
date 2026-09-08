import uuid

from app.core.enums import UserRole
from app.core.exceptions import DuplicateResourceError, InvalidCredentialsError
from app.core.security import (
    InvalidTokenError,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse


class AuthService:
    def __init__(self, user_repository: UserRepository):
        self._users = user_repository

    async def register(self, email: str, password: str) -> User:
        existing = await self._users.get_by_email(email)
        if existing is not None:
            raise DuplicateResourceError(f"Account with email {email} already exists")

        return await self._users.create(
            email=email,
            hashed_password=hash_password(password),
            role=UserRole.CUSTOMER.value,
        )

    async def login(self, email: str, password: str) -> TokenResponse:
        user = await self._users.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        return self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token, TokenType.REFRESH)
        except InvalidTokenError as exc:
            raise InvalidCredentialsError("Invalid or expired refresh token") from exc

        try:
            user_id = uuid.UUID(payload["sub"])
        except ValueError as exc:
            raise InvalidCredentialsError("Invalid or expired refresh token") from exc

        user = await self._users.get_by_id(user_id)
        if user is None:
            raise InvalidCredentialsError("Invalid or expired refresh token")

        return self._issue_tokens(user)

    def _issue_tokens(self, user: User) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(str(user.id), user.role),
            refresh_token=create_refresh_token(str(user.id), user.role),
        )
