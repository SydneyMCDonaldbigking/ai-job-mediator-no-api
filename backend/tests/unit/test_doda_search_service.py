import asyncio
import importlib
from pathlib import Path
import sys
import types

import pytest

litellm_module = types.ModuleType("litellm")
litellm_module.Router = type("Router", (), {})
litellm_module.acompletion = None
litellm_module.get_model_info = lambda model: {}

litellm_router_module = types.ModuleType("litellm.router")
litellm_router_module.RetryPolicy = type("RetryPolicy", (), {})

sys.modules.setdefault("litellm", litellm_module)
sys.modules.setdefault("litellm.router", litellm_router_module)

from app.ai.tasks import GeneratedSearchQueries
from app.ai.tasks.generate_search_queries import generate_search_queries as real_generate_search_queries
from app.schemas.models import ResumeData, SeekRawJob

seek_search_module = importlib.import_module("app.career_ops.seek_search")
doda_search_module = importlib.import_module("app.career_ops.doda_search")

build_doda_search_plan = doda_search_module.build_doda_search_plan
build_doda_search_url = doda_search_module.build_doda_search_url
localize_location_for_doda = doda_search_module.localize_location_for_doda
normalize_doda_job = doda_search_module.normalize_doda_job
parse_doda_list_html = doda_search_module.parse_doda_list_html
run_manual_doda_search = doda_search_module.run_manual_doda_search
scrape_doda_search_results = doda_search_module.scrape_doda_search_results


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_build_doda_search_plan_uses_ai_generated_queries_and_preserves_localized_location(
    monkeypatch: pytest.MonkeyPatch,
):
    resume = ResumeData.model_validate(
        {
            "summary": "Python FastAPI backend engineer building APIs on AWS.",
            "workExperience": [
                {
                    "id": 1,
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "years": "2022-Present",
                    "description": ["Built APIs", "Improved AWS platform tooling"],
                }
            ],
            "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
        }
    )

    localized_tokyo = localize_location_for_doda(country="JP", location_text="Tokyo")
    localized_osaka = localize_location_for_doda(country="JP", location_text="Osaka")

    async def fake_generate_search_queries(*, resume, language, default_location):
        assert language == "ja"
        assert default_location == localized_tokyo
        return GeneratedSearchQueries(
            candidate_profile_summary="AI generated Japanese profile",
            keywords=["AI keyword 1", "AI keyword 2"],
            location=localized_osaka,
        )

    monkeypatch.setattr(doda_search_module, "generate_search_queries", fake_generate_search_queries)

    plan = await build_doda_search_plan(
        resume,
        resume_id="resume-ja-1",
        country="JP",
        location_text="Tokyo",
    )

    assert plan.source == "doda"
    assert plan.location == localized_tokyo
    assert plan.candidate_profile_summary == "AI generated Japanese profile"
    assert plan.keywords == ["AI keyword 1", "AI keyword 2"]


def test_localize_location_for_doda_maps_common_city():
    assert localize_location_for_doda(country="jp", location_text="tokyo") == "東京"
    assert localize_location_for_doda(country="JP", location_text="TOKYO") == "東京"
    assert localize_location_for_doda(country=" jp ", location_text=" Tokyo ") == "東京"
    assert localize_location_for_doda(country="JP", location_text="Osaka") == "大阪"
    assert localize_location_for_doda(country="JP", location_text="Kyoto") == "京都"
    assert localize_location_for_doda(country="JP", location_text="Nagoya") == "名古屋"


def test_build_doda_search_url_uses_current_keyword_route():
    url = build_doda_search_url(keyword="Python API開発", location="東京")

    assert url == "https://doda.jp/DodaFront/View/JobSearchList/j_k__/Python%20API%E9%96%8B%E7%99%BA/"


@pytest.mark.anyio
async def test_build_doda_search_plan_uses_japanese_task_fallback_keywords(
    monkeypatch: pytest.MonkeyPatch,
):
    localized_tokyo = localize_location_for_doda(country="JP", location_text="Tokyo")
    resume = ResumeData.model_validate(
        {
            "summary": "Python FastAPI backend engineer building APIs on AWS.",
            "workExperience": [
                {
                    "id": 1,
                    "title": "Backend Engineer",
                    "company": "Acme",
                    "years": "2022-Present",
                    "description": ["Built APIs", "Improved AWS platform tooling"],
                }
            ],
            "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
        }
    )

    generate_search_queries_module = importlib.import_module("app.ai.tasks.generate_search_queries")

    class FakeRunnable:
        async def ainvoke(self, task_input) -> dict[str, object]:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        generate_search_queries_module,
        "build_generate_search_queries_runnable",
        lambda: FakeRunnable(),
    )
    monkeypatch.setattr(doda_search_module, "generate_search_queries", real_generate_search_queries)

    plan = await build_doda_search_plan(
        resume,
        resume_id="resume-ja-fallback",
        country="JP",
        location_text="TOKYO",
    )

    assert plan.location == localized_tokyo
    assert len(plan.keywords) >= 2
    assert "バックエンドエンジニア" in plan.keywords
    assert "python エンジニア" in plan.keywords
    assert all(keyword.isascii() is False for keyword in plan.keywords[:2])
    assert "engineer" not in " ".join(plan.keywords).lower()


@pytest.mark.anyio
async def test_run_manual_doda_search_preserves_localized_explicit_location_in_scrape(
    monkeypatch: pytest.MonkeyPatch,
):
    captured_calls: list[tuple[str, str]] = []
    localized_tokyo = localize_location_for_doda(country="JP", location_text="Tokyo")
    localized_osaka = localize_location_for_doda(country="JP", location_text="Osaka")

    monkeypatch.setattr(
        doda_search_module.db,
        "get_resume",
        lambda resume_id: {
            "processed_data": {
                "summary": "Python backend engineer",
                "workExperience": [
                    {
                        "id": 1,
                        "title": "Backend Engineer",
                        "company": "Acme",
                        "years": "2022-Present",
                        "description": ["Built APIs", "Worked on AWS"],
                    }
                ],
                "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
            }
        },
    )

    async def fake_generate_search_queries(*, resume, language, default_location):
        assert language == "ja"
        assert default_location == localized_tokyo
        return GeneratedSearchQueries(
            candidate_profile_summary="AI generated Japanese profile",
            keywords=["AI keyword 1", "AI keyword 2"],
            location=localized_osaka,
        )

    async def fake_scrape_doda_search_results(*, keyword: str, location: str):
        captured_calls.append((keyword, location))
        return [
            SeekRawJob(
                search_keyword=keyword,
                title="Backend Engineer",
                company="Example",
                location=location,
                job_url=f"https://doda.jp/job/{len(captured_calls)}",
            )
        ]

    monkeypatch.setattr(doda_search_module, "generate_search_queries", fake_generate_search_queries)
    monkeypatch.setattr(doda_search_module, "scrape_doda_search_results", fake_scrape_doda_search_results)

    response = await run_manual_doda_search(resume_id="resume-ja-1", location="Tokyo")

    assert response.plan.location == localized_tokyo
    assert captured_calls == [
        ("AI keyword 1", localized_tokyo),
        ("AI keyword 2", localized_tokyo),
    ]


@pytest.mark.anyio
async def test_run_manual_doda_search_scrapes_keywords_concurrently(
    monkeypatch: pytest.MonkeyPatch,
):
    active = 0
    max_active = 0

    monkeypatch.setattr(
        doda_search_module.db,
        "get_resume",
        lambda resume_id: {
            "processed_data": {
                "summary": "Python backend engineer",
                "workExperience": [],
                "additional": {"technicalSkills": ["Python", "FastAPI"]},
            }
        },
    )

    async def fake_generate_search_queries(*, resume, language, default_location):
        return GeneratedSearchQueries(
            candidate_profile_summary="profile",
            keywords=["バックエンドエンジニア", "Python"],
            location=default_location,
        )

    async def fake_scrape_doda_search_results(*, keyword: str, location: str):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        try:
            await asyncio.sleep(0.05)
        finally:
            active -= 1
        return [
            SeekRawJob(
                search_keyword=keyword,
                title="Backend Engineer",
                company="Example",
                location=location,
                job_url=f"https://doda.jp/job/{keyword}",
            )
        ]

    monkeypatch.setattr(doda_search_module, "generate_search_queries", fake_generate_search_queries)
    monkeypatch.setattr(doda_search_module, "scrape_doda_search_results", fake_scrape_doda_search_results)
    monkeypatch.setattr(doda_search_module, "is_search_fallback_configured", lambda: False)

    response = await run_manual_doda_search(resume_id="resume-ja-1")

    assert max_active == 2
    assert response.stats.queries_succeeded == 2


@pytest.mark.anyio
async def test_run_manual_doda_search_reports_empty_exception_names(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        doda_search_module.db,
        "get_resume",
        lambda resume_id: {
            "processed_data": {
                "summary": "Python backend engineer",
                "workExperience": [],
                "additional": {"technicalSkills": ["Python"]},
            }
        },
    )

    async def fake_generate_search_queries(*, resume, language, default_location):
        return GeneratedSearchQueries(
            candidate_profile_summary="profile",
            keywords=["Python"],
            location=default_location,
        )

    async def fake_scrape_doda_search_results(*, keyword: str, location: str):
        raise TimeoutError()

    monkeypatch.setattr(doda_search_module, "generate_search_queries", fake_generate_search_queries)
    monkeypatch.setattr(doda_search_module, "scrape_doda_search_results", fake_scrape_doda_search_results)
    monkeypatch.setattr(doda_search_module, "is_search_fallback_configured", lambda: False)

    response = await run_manual_doda_search(resume_id="resume-ja-1")

    assert response.errors[0].message == "TimeoutError"


@pytest.mark.anyio
async def test_run_manual_doda_search_uses_search_fallback_when_direct_scrape_fails(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        doda_search_module.db,
        "get_resume",
        lambda resume_id: {
            "processed_data": {
                "summary": "Python backend engineer",
                "workExperience": [],
                "additional": {"technicalSkills": ["Python"]},
            }
        },
    )

    async def fake_generate_search_queries(*, resume, language, default_location):
        return GeneratedSearchQueries(
            candidate_profile_summary="profile",
            keywords=["バックエンドエンジニア"],
            location=default_location,
        )

    async def failed_scrape(*, keyword: str, location: str):
        raise TimeoutError()

    async def fake_search_fallback(*, source: str, keyword: str, location: str):
        assert source == "doda"
        assert keyword == "バックエンドエンジニア"
        return [
            SeekRawJob(
                search_keyword=keyword,
                title="バックエンドエンジニア",
                company="株式会社オープンAI",
                location=location,
                job_url="https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__3012345678/",
            )
        ]

    monkeypatch.setattr(doda_search_module, "generate_search_queries", fake_generate_search_queries)
    monkeypatch.setattr(doda_search_module, "scrape_doda_search_results", failed_scrape)
    monkeypatch.setattr(doda_search_module, "is_search_fallback_configured", lambda: True)
    monkeypatch.setattr(doda_search_module, "search_jobs_via_fallback", fake_search_fallback)

    response = await run_manual_doda_search(resume_id="resume-ja-1")

    assert response.stats.queries_succeeded == 1
    assert response.errors == []
    assert response.jobs[0].job_url == "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__3012345678/"


def test_parse_doda_list_html_extracts_required_fields():
    html = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "doda"
        / "list_page_sample.html"
    ).read_text(encoding="utf-8")

    jobs = parse_doda_list_html(
        html,
        base_url="https://doda.jp",
        search_keyword="backend engineer",
    )

    assert len(jobs) == 1
    assert jobs[0].title == "バックエンドエンジニア"
    assert jobs[0].company == "OpenAI Japan"
    assert jobs[0].location == "東京都"
    assert jobs[0].is_new is True


def test_parse_doda_list_html_extracts_current_detail_links():
    html = """
    <html><body>
      <a href="/DodaFront/View/JobSearchDetail/j_jid__123/">
        株式会社オープンAI バックエンドエンジニア／Python API開発
      </a>
      <p>募集要項</p>
      <p>FastAPI と AWS を用いたWebサービス開発</p>
      <a href="/DodaFront/View/JobSearchDetail/j_jid__123/">応募する</a>
    </body></html>
    """

    jobs = parse_doda_list_html(
        html,
        base_url="https://doda.jp",
        search_keyword="Python API開発",
    )

    assert len(jobs) == 1
    assert jobs[0].title == "バックエンドエンジニア／Python API開発"
    assert jobs[0].company == "株式会社オープンAI"
    assert jobs[0].job_url == "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__123/"


@pytest.mark.anyio
async def test_scrape_doda_search_results_uses_http_fetch_before_browser(
    monkeypatch: pytest.MonkeyPatch,
):
    captured_urls: list[str] = []

    async def fake_fetch_html(url: str) -> str:
        captured_urls.append(url)
        return """
        <a href="/DodaFront/View/JobSearchDetail/j_jid__123/">
          株式会社オープンAI バックエンドエンジニア／Python
        </a>
        """

    async def fail_browser_fetch(url: str) -> str:
        raise AssertionError("browser fallback should not be used")

    monkeypatch.setattr(doda_search_module, "fetch_doda_search_html", fake_fetch_html)
    monkeypatch.setattr(doda_search_module, "fetch_doda_search_html_with_browser", fail_browser_fetch)

    jobs = await scrape_doda_search_results(keyword="Python", location="東京")

    assert captured_urls == ["https://doda.jp/DodaFront/View/JobSearchList/j_k__/Python/"]
    assert len(jobs) == 1
    assert jobs[0].company == "株式会社オープンAI"


def test_normalize_doda_job_sets_source_and_job_id():
    normalized = normalize_doda_job(
        {
            "title": "Backend Engineer",
            "company": "OpenAI Japan",
            "job_url": "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__123/",
            "location": localize_location_for_doda(country="JP", location_text="Tokyo"),
            "salary": "700-1000",
            "summary": "Python / FastAPI",
            "search_keyword": "backend engineer",
            "is_new": True,
        }
    )

    assert normalized.source == "doda"
    assert normalized.job_id.startswith("doda:")
    assert normalized.match_score == 0.0
