
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app import app


@pytest.mark.asyncio
async def test_health_check():
    """Test the /health endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # We need to mock the dependency if we don't want real Kaggle calls
        with patch("app.get_kaggle_service") as mock_dep:
            mock_service = MagicMock()
            mock_service.get_client.return_value = True # Simulate success
            mock_dep.return_value = mock_service

            response = await client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "dependencies" in data
            assert "redis" in data["dependencies"]

@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test the /metrics endpoint."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "api_requests_total" in response.text

@pytest.mark.asyncio
async def test_get_context_validation():
    """Test input validation for /get-context."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Missing URL
        response = await client.get("/get-context")
        assert response.status_code == 422

        # Invalid Format
        response = await client.get("/get-context?url=https://kaggle.com&output_format=invalid")
        assert response.status_code == 422

# Note: We skip full end-to-end of get_context here as it requires complex mocking of
# loop.run_in_executor and FileResponse generation which is better covered by
# the unit tests of the service itself (test_integration.py).
