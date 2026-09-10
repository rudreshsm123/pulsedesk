import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

# Auth-rejection path that fails before any database access, so it runs without a
# live Postgres (matches tests/api/test_tickets_validation.py's rationale).


@pytest.mark.asyncio
async def test_list_agents_without_auth_is_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/users/agents")

    assert response.status_code == 401
