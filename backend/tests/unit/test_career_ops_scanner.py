"""Unit tests for Career Ops portal scanning helpers."""

import asyncio
from pathlib import Path

import pytest

import app.career_ops.scanner as scanner_module
from app.career_ops.scanner import (
    build_title_filter,
    detect_api,
    ensure_portals_config,
    parse_greenhouse_jobs,
    scan_portals,
)


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_detect_api_handles_greenhouse_ashby_and_lever():
    assert detect_api({"api": "https://boards-api.greenhouse.io/v1/boards/acme/jobs"}) == {
        "type": "greenhouse",
        "url": "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
    }
    assert detect_api({"careers_url": "https://jobs.ashbyhq.com/acme"}) == {
        "type": "ashby",
        "url": "https://api.ashbyhq.com/posting-api/job-board/acme?includeCompensation=true",
    }
    assert detect_api({"careers_url": "https://jobs.lever.co/acme"}) == {
        "type": "lever",
        "url": "https://api.lever.co/v0/postings/acme",
    }


def test_build_title_filter_applies_positive_and_negative_keywords():
    matcher = build_title_filter(
        {
            "positive": ["AI Engineer", "Solutions Architect"],
            "negative": ["Junior", "Intern"],
        }
    )

    assert matcher("Senior AI Engineer") is True
    assert matcher("Junior AI Engineer") is False
    assert matcher("Backend Platform Engineer") is False


def test_parse_greenhouse_jobs_normalizes_payload():
    jobs = parse_greenhouse_jobs(
        {
            "jobs": [
                {
                    "title": "Senior AI Engineer",
                    "absolute_url": "https://jobs.example.com/1",
                    "location": {"name": "Remote"},
                }
            ]
        },
        company_name="Acme",
    )

    assert jobs == [
        {
            "title": "Senior AI Engineer",
            "url": "https://jobs.example.com/1",
            "company": "Acme",
            "location": "Remote",
            "source": "greenhouse",
        }
    ]


def test_ensure_portals_config_bootstraps_example():
    config_path = Path("backend/data/test-portals.yml")
    example_path = Path("backend/data/test-portals.example.yml")
    config_path.unlink(missing_ok=True)
    example_path.unlink(missing_ok=True)
    try:
        example_path.write_text("title_filter:\n  positive:\n    - AI\n", encoding="utf-8")

        result_path = ensure_portals_config(config_path=config_path, example_path=example_path)

        assert result_path == config_path
        assert config_path.exists()
        assert "positive" in config_path.read_text(encoding="utf-8")
    finally:
        config_path.unlink(missing_ok=True)
        example_path.unlink(missing_ok=True)


@pytest.mark.anyio
async def test_scan_portals_fetches_company_apis_concurrently(
    monkeypatch: pytest.MonkeyPatch,
):
    active = 0
    max_active = 0
    history_path = Path("backend/data/test-scan-history-concurrent.tsv")
    history_path.unlink(missing_ok=True)

    class FakeResponse:
        def __init__(self, url: str):
            self.url = url

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            suffix = self.url.rsplit("/", 2)[-2]
            return {
                "jobs": [
                    {
                        "title": "Senior Backend Engineer",
                        "absolute_url": f"https://jobs.example.com/{suffix}",
                        "location": {"name": "Remote"},
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *args: object, **kwargs: object):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object):
            return None

        async def get(self, url: str):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            try:
                await asyncio.sleep(0.05)
            finally:
                active -= 1
            return FakeResponse(url)

    monkeypatch.setattr(scanner_module.httpx, "AsyncClient", FakeAsyncClient)

    try:
        result = await scan_portals(
            config={
                "title_filter": {"positive": ["Backend"], "negative": []},
                "tracked_companies": [
                    {
                        "name": "Acme",
                        "enabled": True,
                        "api": "https://boards-api.greenhouse.io/v1/boards/acme/jobs",
                    },
                    {
                        "name": "Beta",
                        "enabled": True,
                        "api": "https://boards-api.greenhouse.io/v1/boards/beta/jobs",
                    },
                ],
            },
            history_path=history_path,
        )
    finally:
        history_path.unlink(missing_ok=True)

    assert max_active == 2
    assert len(result.new_offers) == 2
