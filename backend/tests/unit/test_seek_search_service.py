import importlib
import importlib.util
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
from app.schemas.models import ResumeData, SeekRawJob

app_module = importlib.import_module("app")
career_ops_package = types.ModuleType("app.career_ops")
career_ops_package.__path__ = [  # type: ignore[attr-defined]
    str(Path(__file__).resolve().parents[2] / "app" / "career_ops")
]
sys.modules.setdefault("app.career_ops", career_ops_package)
setattr(app_module, "career_ops", career_ops_package)

seek_search_path = (
    Path(__file__).resolve().parents[2] / "app" / "career_ops" / "seek_search.py"
)
seek_search_spec = importlib.util.spec_from_file_location(
    "app.career_ops.seek_search",
    seek_search_path,
)
assert seek_search_spec is not None and seek_search_spec.loader is not None
seek_search_module = importlib.util.module_from_spec(seek_search_spec)
sys.modules["app.career_ops.seek_search"] = seek_search_module
seek_search_spec.loader.exec_module(seek_search_module)
setattr(career_ops_package, "seek_search", seek_search_module)

build_seek_search_plan = seek_search_module.build_seek_search_plan
dedupe_seek_jobs = seek_search_module.dedupe_seek_jobs
parse_seek_list_html = seek_search_module.parse_seek_list_html
run_manual_seek_search = seek_search_module.run_manual_seek_search
score_seek_job = seek_search_module.score_seek_job


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_build_seek_search_plan_uses_ai_generated_queries(
    monkeypatch: pytest.MonkeyPatch,
):
    resume = ResumeData.model_validate(
        {
            "summary": "Senior backend engineer building Python APIs and platform services.",
            "workExperience": [
                {
                    "id": 1,
                    "title": "Senior Backend Engineer",
                    "company": "Acme",
                    "years": "2022-Present",
                    "description": ["Built FastAPI services", "Improved AWS platform tooling"],
                }
            ],
            "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
        }
    )

    async def fake_generate_search_queries(*, resume, language, default_location):
        assert language == "en"
        assert default_location == "Brisbane QLD"
        return GeneratedSearchQueries(
            candidate_profile_summary="AI generated profile",
            keywords=["ml engineer", "data platform engineer"],
            location="Melbourne VIC",
        )

    monkeypatch.setattr(
        seek_search_module,
        "generate_search_queries",
        fake_generate_search_queries,
    )

    plan = await build_seek_search_plan(
        resume,
        resume_id="resume-1",
        location="Brisbane QLD",
    )

    assert plan.source == "seek"
    assert plan.location == "Brisbane QLD"
    assert plan.candidate_profile_summary == "AI generated profile"
    assert plan.keywords == ["ml engineer", "data platform engineer"]


@pytest.mark.anyio
async def test_run_manual_seek_search_forwards_explicit_location_to_scrape(
    monkeypatch: pytest.MonkeyPatch,
):
    captured_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        seek_search_module.db,
        "get_resume",
        lambda resume_id: {
            "processed_data": {
                "summary": "Senior backend engineer building Python APIs and platform services.",
                "workExperience": [
                    {
                        "id": 1,
                        "title": "Senior Backend Engineer",
                        "company": "Acme",
                        "years": "2022-Present",
                        "description": [
                            "Built FastAPI services",
                            "Improved AWS platform tooling",
                        ],
                    }
                ],
                "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
            }
        },
    )

    async def fake_generate_search_queries(*, resume, language, default_location):
        assert language == "en"
        assert default_location == "Brisbane QLD"
        return GeneratedSearchQueries(
            candidate_profile_summary="AI generated profile",
            keywords=["ml engineer", "data platform engineer"],
            location="Melbourne VIC",
        )

    async def fake_scrape_seek_search_results(*, keyword: str, location: str):
        captured_calls.append((keyword, location))
        return [
            SeekRawJob(
                search_keyword=keyword,
                title="ML Engineer",
                company="Example",
                location=location,
                job_url=f"https://www.seek.com.au/job/{len(captured_calls)}",
            )
        ]

    monkeypatch.setattr(
        seek_search_module,
        "generate_search_queries",
        fake_generate_search_queries,
    )
    monkeypatch.setattr(
        seek_search_module,
        "scrape_seek_search_results",
        fake_scrape_seek_search_results,
    )

    response = await run_manual_seek_search(
        resume_id="resume-1",
        location="Brisbane QLD",
    )

    assert response.plan.location == "Brisbane QLD"
    assert captured_calls == [
        ("ml engineer", "Brisbane QLD"),
        ("data platform engineer", "Brisbane QLD"),
    ]


def test_dedupe_seek_jobs_prefers_unique_job_url():
    jobs = [
        SeekRawJob(
            search_keyword="python backend engineer",
            title="Senior Backend Engineer",
            company="Example",
            location="Sydney NSW",
            job_url="https://www.seek.com.au/job/123",
        ),
        SeekRawJob(
            search_keyword="platform engineer",
            title="Senior Backend Engineer",
            company="Example",
            location="Sydney NSW",
            job_url="https://www.seek.com.au/job/123",
        ),
    ]

    deduped = dedupe_seek_jobs(jobs)

    assert len(deduped) == 1


def test_score_seek_job_rewards_skill_overlap():
    resume = ResumeData.model_validate(
        {
            "summary": "Python backend engineer",
            "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
        }
    )
    job = SeekRawJob(
        search_keyword="python backend engineer",
        title="Senior Backend Engineer",
        company="Example",
        location="Sydney NSW",
        summary="Build Python and FastAPI services on AWS.",
        job_url="https://www.seek.com.au/job/123",
    )

    score = score_seek_job(job, resume, location="Sydney NSW")

    assert score > 0.5


def test_parse_seek_list_html_extracts_job_cards():
    html = (
        Path(__file__).resolve().parents[1]
        / "fixtures"
        / "seek"
        / "list_page_sample.html"
    ).read_text(encoding="utf-8")

    jobs = parse_seek_list_html(
        html,
        base_url="https://www.seek.com.au",
        search_keyword="python backend engineer",
    )

    assert jobs[0].title == "Senior Backend Engineer"
    assert jobs[0].company == "Example Co"
    assert jobs[0].job_url.startswith("https://www.seek.com.au/job/")
