import uuid

import pytest

from app.api.deps import require_role
from app.core.enums import UserRole
from app.core.exceptions import UnauthorizedActionError
from app.models.user import User


def make_user(role: UserRole) -> User:
    return User(id=uuid.uuid4(), email="u@example.com", hashed_password="x", role=role.value)


@pytest.mark.asyncio
async def test_require_role_allows_matching_role():
    checker = require_role(UserRole.AGENT, UserRole.ADMIN)
    user = make_user(UserRole.AGENT)

    result = await checker(user=user)

    assert result is user


@pytest.mark.asyncio
async def test_require_role_rejects_non_matching_role():
    checker = require_role(UserRole.ADMIN)
    user = make_user(UserRole.CUSTOMER)

    with pytest.raises(UnauthorizedActionError):
        await checker(user=user)
