import pytest

from app.core.enums import UserRole
from app.core.exceptions import DuplicateResourceError, InvalidCredentialsError
from app.core.security import TokenType, decode_token, hash_password
from app.services.auth_service import AuthService
from tests.fakes import FakeUserRepository


@pytest.fixture
def auth_service() -> AuthService:
    return AuthService(FakeUserRepository())


@pytest.mark.asyncio
async def test_register_creates_customer(auth_service: AuthService):
    user = await auth_service.register("new@example.com", "password123")

    assert user.email == "new@example.com"
    assert user.role == UserRole.CUSTOMER.value


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email(auth_service: AuthService):
    await auth_service.register("dup@example.com", "password123")

    with pytest.raises(DuplicateResourceError):
        await auth_service.register("dup@example.com", "another-password")


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_password(auth_service: AuthService):
    await auth_service.register("agent@example.com", "correct-password")

    tokens = await auth_service.login("agent@example.com", "correct-password")

    payload = decode_token(tokens.access_token, TokenType.ACCESS)
    assert payload["role"] == UserRole.CUSTOMER.value


@pytest.mark.asyncio
async def test_login_rejects_wrong_password(auth_service: AuthService):
    await auth_service.register("agent2@example.com", "correct-password")

    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("agent2@example.com", "wrong-password")


@pytest.mark.asyncio
async def test_login_rejects_unknown_email(auth_service: AuthService):
    with pytest.raises(InvalidCredentialsError):
        await auth_service.login("nobody@example.com", "whatever")


@pytest.mark.asyncio
async def test_refresh_issues_new_token_pair(auth_service: AuthService):
    user = await auth_service.register("refresh@example.com", "password123")
    tokens = await auth_service.login("refresh@example.com", "password123")

    new_tokens = await auth_service.refresh(tokens.refresh_token)

    payload = decode_token(new_tokens.access_token, TokenType.ACCESS)
    assert payload["sub"] == str(user.id)


@pytest.mark.asyncio
async def test_refresh_rejects_access_token_used_as_refresh(auth_service: AuthService):
    await auth_service.register("x@example.com", "password123")
    tokens = await auth_service.login("x@example.com", "password123")

    with pytest.raises(InvalidCredentialsError):
        await auth_service.refresh(tokens.access_token)


def test_password_is_hashed_not_stored_plain():
    hashed = hash_password("plaintext")
    assert hashed != "plaintext"
