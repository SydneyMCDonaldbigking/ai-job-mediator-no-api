from __future__ import annotations

import argparse
import copy
from pathlib import Path
import shutil
import sys

import uvicorn


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


SAMPLE_RESUME = {
    "personalInfo": {
        "name": "Jane Doe",
        "title": "Senior Backend Engineer",
        "email": "jane@example.com",
        "phone": "+1-555-0100",
        "location": "San Francisco, CA",
        "website": "https://janedoe.dev",
        "linkedin": "linkedin.com/in/janedoe",
        "github": "github.com/janedoe",
    },
    "summary": "Backend engineer with 6 years of experience building scalable Python APIs.",
    "workExperience": [
        {
            "id": 1,
            "title": "Senior Backend Engineer",
            "company": "Acme Corp",
            "location": "San Francisco, CA",
            "years": "Jan 2021 - Present",
            "description": [
                "Built REST APIs using Python and FastAPI.",
                "Improved service reliability and deployment safety.",
            ],
        }
    ],
    "education": [
        {
            "id": 1,
            "institution": "MIT",
            "degree": "B.S. Computer Science",
            "years": "2014 - 2018",
            "description": "Graduated with honors",
        }
    ],
    "personalProjects": [
        {
            "id": 1,
            "name": "OpenAPI Generator",
            "role": "Creator",
            "years": "2021 - Present",
            "description": ["CLI tool for OpenAPI clients."],
        }
    ],
    "additional": {
        "technicalSkills": ["Python", "FastAPI", "Docker", "AWS"],
        "languages": ["English"],
        "certificationsTraining": [],
        "awards": [],
    },
    "customSections": {},
    "sectionMeta": [],
}


def _build_tailored_resume(job_description: str) -> dict:
    resume = copy.deepcopy(SAMPLE_RESUME)
    jd_text = " ".join(job_description.split())
    resume["summary"] = (
        "Tailored backend engineer profile aligned to the target role. "
        f"Focus: {jd_text[:120]}"
    )
    skills = resume["additional"]["technicalSkills"]
    if "distributed" in job_description.casefold() and "Distributed Systems" not in skills:
        skills.append("Distributed Systems")
    return resume


async def fake_parse_document(content: bytes, filename: str) -> str:
    del content
    return (
        f"# Jane Doe\n"
        f"Imported from {filename}\n\n"
        "Senior Backend Engineer\n"
        "Skills: Python, FastAPI, Docker, AWS\n"
    )


async def fake_parse_resume_to_json(markdown_text: str) -> dict:
    del markdown_text
    return copy.deepcopy(SAMPLE_RESUME)


async def fake_extract_job_keywords(job_description: str) -> dict:
    return {
        "required_skills": ["Python", "FastAPI", "Docker"],
        "preferred_skills": ["AWS"],
        "key_responsibilities": [
            "Build APIs",
            "Improve platform reliability",
        ],
        "keywords": ["python", "fastapi", "backend"],
        "experience_years": 5,
        "seniority_level": "senior",
        "job_description": job_description,
    }


async def fake_improve_resume(
    *,
    original_resume: str,
    job_description: str,
    job_keywords: dict,
    language: str,
    prompt_id: str,
    original_resume_data: dict | None,
) -> dict:
    del original_resume, job_keywords, language, prompt_id, original_resume_data
    return _build_tailored_resume(job_description)


async def fake_generate_auxiliary_messages(
    improved_data: dict,
    job_content: str,
    language: str,
    enable_cover_letter: bool,
    enable_outreach: bool,
) -> tuple[str | None, str | None, str | None, list[str]]:
    del improved_data, job_content, language, enable_cover_letter, enable_outreach
    return None, None, "Tailored Backend Resume", []


def fake_get_original_resume_data(_: dict) -> None:
    return None


async def fake_generate_tailored_resume_pdf(
    *,
    resume,
    job_description: str,
    page_size: str = "A4",
):
    del resume, page_size
    from app.schemas.models import ResumeData, TailoredPDFResult

    return TailoredPDFResult(
        filename="tailored_resume.pdf",
        pdf_bytes=b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n",
        tailored_resume=ResumeData.model_validate(_build_tailored_resume(job_description)),
        keyword_targets=["Python", "FastAPI"],
    )


async def fake_evaluate_job_fit(*, resume, job_description: str):
    del resume
    from app.schemas.models import (
        CareerOpsEvaluationData,
        CareerOpsMarketData,
        CareerOpsMarketSource,
        CareerOpsScoreDimension,
    )

    return CareerOpsEvaluationData(
        overall_score=4.2,
        overall_label="strong-match",
        executive_summary="Strong backend fit in smoke mode.",
        archetype="backend-platform",
        af_scores={"A": 4.5, "B": 4.0, "C": 4.0, "D": 3.5, "E": 4.5, "F": 4.5},
        dimensions=[
            CareerOpsScoreDimension(
                key="backend_fit",
                category="A",
                label="Backend Fit",
                score=4.5,
                rationale="Smoke backend stub matched Python/FastAPI responsibilities.",
                evidence=[job_description[:100]],
                risks=[],
            )
        ],
        tailoring_priorities=["Move Python/FastAPI achievements higher."],
        interview_focus=["Discuss API ownership and reliability work."],
        keyword_targets=["Python", "FastAPI"],
        market_data=CareerOpsMarketData(
            role_query="Backend Engineer",
            company_name="Smoke Company",
            salary_mentions=["$180,000 base"],
            demand_summary="Demand remains strong for backend platform hiring.",
            compensation_summary="Compensation looks competitive in smoke mode.",
            sources=[
                CareerOpsMarketSource(
                    title="Mock market source",
                    url="https://example.com/market",
                    snippet=job_description[:80],
                )
            ],
        ),
    )


async def fake_run_manual_seek_search(*, resume_id: str, location: str | None = None):
    del resume_id
    from app.schemas.models import (
        SeekManualSearchResponse,
        SeekSearchError,
        SeekSearchJob,
        SeekSearchPlan,
        SeekSearchStats,
    )

    return SeekManualSearchResponse(
        plan=SeekSearchPlan(
            resume_id="smoke-resume",
            source="seek",
            candidate_profile_summary="Python backend engineer with API and platform experience.",
            keywords=["python backend engineer", "platform engineer"],
            location=location or "Sydney NSW",
        ),
        jobs=[
            SeekSearchJob(
                job_id="seek:https://www.seek.com.au/job/123",
                source="seek",
                search_keyword="python backend engineer",
                title="Senior Backend Engineer",
                company="Example Co",
                location=location or "Sydney NSW",
                salary="$180k-$200k",
                work_type="Full time",
                listed_at="2d ago",
                job_url="https://www.seek.com.au/job/123",
                summary="Build APIs and platform services.",
                match_score=0.91,
            )
        ],
        stats=SeekSearchStats(
            keywords_generated=2,
            queries_attempted=2,
            queries_succeeded=2,
            raw_jobs_found=3,
            jobs_after_dedupe=1,
        ),
        errors=[],
    )


def patch_application_for_smoke() -> None:
    import app.routers.career_ops as career_ops_router
    import app.routers.jobs as jobs_router
    import app.routers.resumes as resumes_router

    resumes_router.parse_document = fake_parse_document
    resumes_router.parse_resume_to_json = fake_parse_resume_to_json
    resumes_router.extract_job_keywords = fake_extract_job_keywords
    resumes_router.improve_resume = fake_improve_resume
    resumes_router._generate_auxiliary_messages = fake_generate_auxiliary_messages
    resumes_router._get_original_resume_data = fake_get_original_resume_data

    career_ops_router.generate_tailored_resume_pdf = fake_generate_tailored_resume_pdf
    career_ops_router.evaluate_job_fit = fake_evaluate_job_fit
    jobs_router.run_manual_seek_search = fake_run_manual_seek_search


def seed_smoke_portals_example() -> None:
    from app.config import settings

    target_path = settings.portals_example_path
    if target_path.exists():
        return

    source_path = BACKEND_DIR / "data" / "portals.example.yml"
    if not source_path.exists():
        raise FileNotFoundError(f"Smoke portals example file not found: {source_path}")

    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, target_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the backend in smoke-test mode.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    from app.main import app

    seed_smoke_portals_example()
    patch_application_for_smoke()

    uvicorn.run(app, host=args.host, port=args.port, log_level="error")


if __name__ == "__main__":
    main()
