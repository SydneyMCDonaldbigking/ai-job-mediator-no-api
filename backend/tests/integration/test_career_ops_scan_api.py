"""Integration tests for Career Ops scan endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.models import CareerOpsScanData, CareerOpsScannedOffer


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@patch("app.routers.career_ops.scan_portals", new_callable=AsyncMock)
async def test_scan_jobs_returns_new_offers(mock_scan, client):
    mock_scan.return_value = CareerOpsScanData(
        scanned_companies=3,
        total_jobs_found=8,
        filtered_out=4,
        duplicates=1,
        new_offers=[
            CareerOpsScannedOffer(
                title="Senior AI Engineer",
                url="https://jobs.example.com/123",
                company="Acme",
                location="Remote",
                source="greenhouse",
            )
        ],
        errors=[],
    )

    async with client:
        response = await client.post("/api/scan-jobs")

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["scanned_companies"] == 3
    assert payload["new_offers"][0]["company"] == "Acme"
