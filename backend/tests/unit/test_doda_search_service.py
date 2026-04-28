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
from app.schemas.models import ResumeData, SeekRawJob
from app.ai.tasks.generate_search_queries import generate_search_queries as real_generate_search_queries

seek_search_module = importlib.import_module("app.career_ops.seek_search")
doda_search_module = importlib.import_module("app.career_ops.doda_search")

build_doda_search_plan = doda_search_module.build_doda_search_plan
localize_location_for_doda = doda_search_module.localize_location_for_doda
normalize_doda_job = doda_search_module.normalize_doda_job
parse_doda_list_html = doda_search_module.parse_doda_list_html
run_manual_doda_search = doda_search_module.run_manual_doda_search


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

    monkeypatch.setattr(
        doda_search_module,
        "generate_search_queries",
        fake_generate_search_queries,
    )

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
    expected = localize_location_for_doda(country="JP", location_text="Tokyo")

    assert localize_location_for_doda(country="jp", location_text="tokyo") == expected
    assert localize_location_for_doda(country="JP", location_text="TOKYO") == expected
    assert localize_location_for_doda(country=" jp ", location_text=" Tokyo ") == expected


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

    generate_search_queries_module = importlib.import_module(
        "app.ai.tasks.generate_search_queries"
    )

    class FakeRunnable:
        async def ainvoke(self, task_input) -> dict[str, object]:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        generate_search_queries_module,
        "build_generate_search_queries_runnable",
        lambda: FakeRunnable(),
    )
    monkeypatch.setattr(
        doda_search_module,
        "generate_search_queries",
        real_generate_search_queries,
    )

    plan = await build_doda_search_plan(
        resume,
        resume_id="resume-ja-fallback",
        country="JP",
        location_text="TOKYO",
    )

    assert plan.location == localized_tokyo
    assert len(plan.keywords) >= 2
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

    monkeypatch.setattr(
        doda_search_module,
        "generate_search_queries",
        fake_generate_search_queries,
    )
    monkeypatch.setattr(
        doda_search_module,
        "scrape_doda_search_results",
        fake_scrape_doda_search_results,
    )

    response = await run_manual_doda_search(
        resume_id="resume-ja-1",
        location="Tokyo",
    )

    assert response.plan.location == localized_tokyo
    assert captured_calls == [
        ("AI keyword 1", localized_tokyo),
        ("AI keyword 2", localized_tokyo),
    ]


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
    assert jobs[0].title
    assert jobs[0].company == "OpenAI Japan"
    assert jobs[0].location
    assert jobs[0].is_new is True


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
