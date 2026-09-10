import uuid

import pytest

from app.repositories.user_repository import UserRepository


@pytest.mark.asyncio
async def test_list_by_role_returns_only_matching_role_sorted_by_email(db_session):
    repo = UserRepository(db_session)
    suffix = uuid.uuid4().hex[:8]
    await repo.create(f"zzz-{suffix}@example.com", "x", "agent")
    await repo.create(f"aaa-{suffix}@example.com", "x", "agent")
    await repo.create(f"customer-{suffix}@example.com", "x", "customer")

    agents = await repo.list_by_role("agent")

    matching = [a for a in agents if a.email.endswith(f"{suffix}@example.com")]
    assert [a.email for a in matching] == [f"aaa-{suffix}@example.com", f"zzz-{suffix}@example.com"]
    assert all(a.role == "agent" for a in matching)
