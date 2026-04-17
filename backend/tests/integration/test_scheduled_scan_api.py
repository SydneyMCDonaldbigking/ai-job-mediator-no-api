from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@patch("app.routers.scheduled_scan.load_scheduled_scan_config")
@patch("app.routers.scheduled_scan.load_multilingual_resume_assets")
@patch("app.routers.scheduled_scan.list_high_score_unapplied_jobs")
@patch("app.routers.scheduled_scan.list_recent_new_jobs")
async def test_get_scheduled_scan_settings(mock_jobs, mock_high_score_jobs, mock_assets, mock_load, client):
    mock_load.return_value = {
        "enabled": True,
        "run_time_local": "09:00",
        "timezone": "Australia/Sydney",
        "seek_enabled": True,
        "doda_enabled": False,
        "boss_enabled": False,
        "feishu_enabled": True,
        "feishu_webhook_url": "https://open.feishu.cn/fake-webhook",
        "high_score_threshold": 0.8,
    }
    mock_assets.return_value = {
        "resume_en_id": "resume-en",
        "resume_ja_id": None,
        "resume_zh_id": None,
    }
    mock_jobs.return_value = []
    mock_high_score_jobs.return_value = []

    async with client:
        response = await client.get("/api/v1/scheduled-scan/settings")

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["run_time_local"] == "09:00"
    assert payload["assets"]["resume_en_id"] == "resume-en"
    assert payload["config"]["feishu_enabled"] is True
    assert payload["config"]["high_score_threshold"] == 0.8


@patch("app.routers.scheduled_scan.save_scheduled_scan_config")
@patch("app.routers.scheduled_scan.load_multilingual_resume_assets")
@patch("app.routers.scheduled_scan.list_high_score_unapplied_jobs")
@patch("app.routers.scheduled_scan.list_recent_new_jobs")
async def test_put_scheduled_scan_settings(mock_jobs, mock_high_score_jobs, mock_assets, mock_save, client):
    mock_save.return_value = {
        "enabled": True,
        "run_time_local": "21:30",
        "timezone": "Australia/Sydney",
        "seek_enabled": True,
        "doda_enabled": False,
        "boss_enabled": False,
        "feishu_enabled": True,
        "feishu_webhook_url": "https://open.feishu.cn/fake-webhook",
        "high_score_threshold": 0.85,
    }
    mock_assets.return_value = {
        "resume_en_id": "resume-en",
        "resume_ja_id": None,
        "resume_zh_id": None,
    }
    mock_jobs.return_value = []
    mock_high_score_jobs.return_value = []

    payload = {
        "enabled": True,
        "run_time_local": "21:30",
        "timezone": "Australia/Sydney",
        "seek_enabled": True,
        "doda_enabled": False,
        "boss_enabled": False,
        "feishu_enabled": True,
        "feishu_webhook_url": "https://open.feishu.cn/fake-webhook",
        "high_score_threshold": 0.85,
    }

    async with client:
        response = await client.put("/api/v1/scheduled-scan/settings", json=payload)

    assert response.status_code == 200
    assert response.json()["config"]["run_time_local"] == "21:30"
    assert response.json()["config"]["feishu_webhook_url"] == "https://open.feishu.cn/fake-webhook"
    assert response.json()["config"]["high_score_threshold"] == 0.85


@patch("app.routers.scheduled_scan.mark_job_status")
async def test_post_discovered_job_status(mock_mark, client):
    mock_mark.return_value = {
        "job_key": "seek:https://www.seek.com.au/job/123",
        "source": "seek",
        "resume_language": "en",
        "title": "Senior Backend Engineer",
        "company": "Example Co",
        "location": "Sydney NSW",
        "job_url": "https://www.seek.com.au/job/123",
        "summary": None,
        "match_score": 0.91,
        "discovered_at": "2026-04-17T00:05:00+00:00",
        "first_seen_at": "2026-04-17T00:05:00+00:00",
        "last_seen_at": "2026-04-17T00:05:00+00:00",
        "is_new": True,
        "status": "applied",
    }

    async with client:
        response = await client.post(
            "/api/v1/scheduled-scan/jobs/status",
            json={
                "job_key": "seek:https://www.seek.com.au/job/123",
                "status": "applied",
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "applied"
