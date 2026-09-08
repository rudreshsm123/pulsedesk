import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user
from app.core.db import get_db
from app.core.enums import UserRole
from app.main import app
from app.models.user import User


async def _fake_db():
    # This request is expected to fail on header validation before any repository
    # method ever touches the session, so a real DB connection is never needed here --
    # overriding get_db keeps this test true to the file's "no live Postgres" contract.
    yield None

# These cover the request-validation and auth-rejection paths that fail before any
# database access happens, so they run without a live Postgres. Full authenticated
# success-path API tests (which do need a real DB) belong in the Phase 9 integration
# suite once Postgres is available via docker-compose/Testcontainers.


@pytest.mark.asyncio
async def test_create_ticket_without_auth_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tickets",
            json={"subject": "Help", "body": "Something broke"},
            headers={"Idempotency-Key": "test-key-1"},
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_ticket_without_idempotency_key_is_rejected():
    # Auth is bypassed via dependency override (a fake authenticated customer) so this
    # test isolates the missing-header validation instead of getting short-circuited by
    # the 401 an unauthenticated request would otherwise hit first.
    fake_customer = User(
        id=uuid.uuid4(), email="c@example.com", hashed_password="x", role=UserRole.CUSTOMER.value
    )
    app.dependency_overrides[get_current_user] = lambda: fake_customer
    app.dependency_overrides[get_db] = _fake_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/tickets",
                json={"subject": "Help", "body": "Something broke"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_ticket_with_invalid_token_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tickets",
            json={"subject": "Help", "body": "Something broke"},
            headers={
                "Idempotency-Key": "test-key-2",
                "Authorization": "Bearer not-a-real-token",
            },
        )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_tickets_without_auth_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/tickets")

    assert response.status_code == 401
