import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_metrics_endpoint_reports_request_counts_by_route_template():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/api/v1/health")
        # A path with a UUID path param: the metric label should be the route template
        # ("/api/v1/tickets/{ticket_id}"), not this literal UUID -- otherwise every
        # distinct ticket ID would mint its own Prometheus time series forever.
        await client.get(f"/api/v1/tickets/{uuid.uuid4()}")

        response = await client.get("/api/v1/metrics")

    assert response.status_code == 200
    body = response.text
    assert 'path="/health"' in body
    assert 'path="/tickets/{ticket_id}"' in body
    assert "http_request_duration_seconds" in body
