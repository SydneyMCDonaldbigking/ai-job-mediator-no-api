from pathlib import Path

from app.career_ops.seek_search import (
    build_seek_search_plan,
    dedupe_seek_jobs,
    parse_seek_list_html,
    score_seek_job,
)
from app.schemas.models import ResumeData, SeekRawJob


def test_build_seek_search_plan_generates_backend_keywords():
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

    plan = build_seek_search_plan(resume, resume_id="resume-1", location="Sydney NSW")

    assert plan.source == "seek"
    assert plan.location == "Sydney NSW"
    assert "python backend engineer" in plan.keywords


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
