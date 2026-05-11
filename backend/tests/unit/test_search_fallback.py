import pytest

from app.career_ops import search_fallback
from app.career_ops.search_fallback import (
    build_job_search_query,
    raw_jobs_from_web_results,
    search_jobs_via_fallback,
)


def test_build_job_search_query_scopes_to_supported_job_sites():
    assert (
        build_job_search_query(
            source="seek",
            keyword="python backend engineer",
            location="Sydney NSW",
        )
        == "site:seek.com.au/job python backend engineer Sydney NSW"
    )
    assert (
        build_job_search_query(
            source="doda",
            keyword="バックエンドエンジニア",
            location="東京",
        )
        == "site:doda.jp/DodaFront/View/JobSearchDetail バックエンドエンジニア 東京"
    )


def test_raw_jobs_from_web_results_filters_seek_job_links():
    jobs = raw_jobs_from_web_results(
        [
            {
                "title": "Senior Backend Engineer | SEEK",
                "url": "https://www.seek.com.au/job/123456",
                "description": "Build Python APIs.",
            },
            {
                "title": "Search listing",
                "url": "https://www.seek.com.au/python-engineer-jobs/in-Sydney-NSW",
                "description": "Listing page.",
            },
        ],
        source="seek",
        search_keyword="python backend engineer",
        location="Sydney NSW",
    )

    assert len(jobs) == 2
    assert jobs[0].title == "Senior Backend Engineer"
    assert jobs[0].company == "SEEK"
    assert jobs[0].job_url == "https://www.seek.com.au/job/123456"
    assert jobs[0].summary == "Build Python APIs."
    assert jobs[1].title == "Search listing"
    assert jobs[1].job_url == "https://www.seek.com.au/python-engineer-jobs/in-Sydney-NSW"


def test_raw_jobs_from_web_results_extracts_doda_company_and_title():
    jobs = raw_jobs_from_web_results(
        [
            {
                "title": "株式会社オープンAI／バックエンドエンジニアの求人情報 － 転職ならdoda",
                "url": "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__3012345678/",
                "description": "Python / FastAPI",
            },
            {
                "title": "doda listing",
                "url": "https://doda.jp/DodaFront/View/JobSearchList/j_k__/Python/",
                "description": "Not a detail page.",
            },
        ],
        source="doda",
        search_keyword="バックエンドエンジニア",
        location="東京",
    )

    assert len(jobs) == 1
    assert jobs[0].title == "バックエンドエンジニア"
    assert jobs[0].company == "株式会社オープンAI"
    assert jobs[0].job_url == "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__3012345678/"


@pytest.mark.anyio
async def test_search_jobs_via_fallback_calls_brave_web_search(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "web": {
                    "results": [
                        {
                            "title": "Senior Backend Engineer | SEEK",
                            "url": "https://www.seek.com.au/job/123456",
                            "description": "Build Python APIs.",
                        }
                    ]
                }
            }

    class FakeAsyncClient:
        def __init__(self, *, timeout: float):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url: str, *, headers: dict[str, str], params: dict[str, object]):
            captured["url"] = url
            captured["headers"] = headers
            captured["params"] = params
            return FakeResponse()

    monkeypatch.setattr(search_fallback.settings, "job_search_fallback_provider", "brave")
    monkeypatch.setattr(search_fallback.settings, "brave_search_api_key", "brave-key")
    monkeypatch.setattr(search_fallback.httpx, "AsyncClient", FakeAsyncClient)

    jobs = await search_jobs_via_fallback(
        source="seek",
        keyword="python backend engineer",
        location="Sydney NSW",
        count=3,
    )

    assert captured["url"] == search_fallback.BRAVE_WEB_SEARCH_URL
    assert captured["headers"]["X-Subscription-Token"] == "brave-key"
    assert captured["params"]["q"] == "site:seek.com.au/job python backend engineer Sydney NSW"
    assert captured["params"]["count"] == 3
    assert jobs[0].job_url == "https://www.seek.com.au/job/123456"


@pytest.mark.anyio
async def test_search_jobs_via_fallback_calls_tavily_search(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "results": [
                    {
                        "title": "Senior Backend Engineer | SEEK",
                        "url": "https://www.seek.com.au/job/654321",
                        "content": "Build Python APIs.",
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *, timeout: float):
            captured["timeout"] = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url: str, *, headers: dict[str, str], json: dict[str, object]):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(search_fallback.settings, "job_search_fallback_provider", "tavily")
    monkeypatch.setattr(search_fallback.settings, "tavily_api_key", "tvly-key")
    monkeypatch.setattr(search_fallback.settings, "tavily_search_depth", "basic")
    monkeypatch.setattr(search_fallback.httpx, "AsyncClient", FakeAsyncClient)

    jobs = await search_jobs_via_fallback(
        source="seek",
        keyword="python backend engineer",
        location="Sydney NSW",
        count=4,
    )

    assert captured["url"] == search_fallback.TAVILY_SEARCH_URL
    assert captured["headers"]["Authorization"] == "Bearer tvly-key"
    assert captured["json"]["query"] == "site:seek.com.au/job python backend engineer Sydney NSW"
    assert captured["json"]["search_depth"] == "basic"
    assert captured["json"]["max_results"] == 4
    assert captured["json"]["include_domains"] == ["seek.com.au"]
    assert jobs[0].job_url == "https://www.seek.com.au/job/654321"
