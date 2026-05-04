"""Integration tests for portals config endpoints."""

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@patch("app.routers.config.load_portals_config")
async def test_get_portals_config(mock_load, client):
    mock_load.return_value = {
        "title_filter": {"positive": ["AI"], "negative": ["Junior"]},
        "tracked_companies": [{"name": "Acme", "careers_url": "https://jobs.example.com"}],
        "search_queries": [],
    }

    async with client:
        response = await client.get("/api/v1/config/portals")

    assert response.status_code == 200
    payload = response.json()
    assert payload["title_filter"]["positive"] == ["AI"]
    assert payload["tracked_companies"][0]["name"] == "Acme"


@patch("app.routers.config.save_portals_config")
async def test_put_portals_config(mock_save, client):
    payload = {
        "title_filter": {"positive": ["AI"], "negative": ["Junior"]},
        "tracked_companies": [{"name": "Acme", "careers_url": "https://jobs.example.com"}],
        "search_queries": [],
    }

    async with client:
        response = await client.put("/api/v1/config/portals", json=payload)

    assert response.status_code == 200
    assert response.json()["tracked_companies"][0]["careers_url"] == "https://jobs.example.com"
    mock_save.assert_called_once()
