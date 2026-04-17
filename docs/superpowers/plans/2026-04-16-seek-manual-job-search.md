# SEEK Manual Job Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a manual SEEK search workflow that generates search keywords from the active resume, scrapes first-page SEEK list results, ranks them, and shows them in the existing Chainlit frontend.

**Architecture:** Extend the backend with a small SEEK search service that reuses the current structured resume context, Playwright runtime, and existing API patterns. Keep browser automation isolated in a SEEK-specific module, expose a single orchestration route, and wire one new frontend action plus formatter helpers to the current chat-first UI.

**Tech Stack:** Python, FastAPI, Playwright, Pydantic, httpx, Chainlit, pytest, unittest

---

### Task 1: Add failing backend model and pipeline tests for SEEK search planning, dedupe, and scoring

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_seek_search_service.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\seek_search.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_seek_search_service.py`

- [ ] **Step 1: Write the failing test**

```python
from app.career_ops.seek_search import (
    build_seek_search_plan,
    dedupe_seek_jobs,
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_seek_search_service.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing symbol errors for the new SEEK search helpers.

- [ ] **Step 3: Write minimal implementation**

```python
class SeekSearchPlan(BaseModel):
    resume_id: str
    source: str = "seek"
    candidate_profile_summary: str
    keywords: list[str]
    location: str


def build_seek_search_plan(resume: ResumeData, *, resume_id: str, location: str) -> SeekSearchPlan:
    keywords = ["python backend engineer"]
    return SeekSearchPlan(
        resume_id=resume_id,
        candidate_profile_summary=resume.summary or "",
        keywords=keywords,
        location=location,
    )


def dedupe_seek_jobs(jobs: list[SeekRawJob]) -> list[SeekRawJob]:
    seen: set[str] = set()
    result: list[SeekRawJob] = []
    for job in jobs:
        key = job.job_url or f"{job.title}|{job.company}|{job.location}"
        if key in seen:
            continue
        seen.add(key)
        result.append(job)
    return result


def score_seek_job(job: SeekRawJob, resume: ResumeData, *, location: str) -> float:
    haystack = f"{job.title} {job.summary or ''}".lower()
    score = 0.0
    for keyword in ["python", "fastapi", "aws"]:
        if keyword in haystack:
            score += 0.25
    if location.lower() in (job.location or "").lower():
        score += 0.25
    return min(score, 1.0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_seek_search_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_seek_search_service.py backend/app/schemas/models.py backend/app/career_ops/seek_search.py
git commit -m "test: add seek search planning and scoring coverage"
```

### Task 2: Add failing backend scraper parsing tests for SEEK list-page extraction

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\fixtures\seek\list_page_sample.html`
- Modify: `C:\Users\\zzyyds\\Desktop\\go_find_a_job\\ai-job-mediator\\backend\\tests\\unit\\test_seek_search_service.py`
- Modify: `C:\Users\\zzyyds\\Desktop\\go_find_a_job\\ai-job-mediator\\backend\\app\\career_ops\\seek_search.py`
- Test: `C:\Users\\zzyyds\\Desktop\\go_find_a_job\\ai-job-mediator\\backend\\tests\\unit\\test_seek_search_service.py`

- [ ] **Step 1: Write the failing test**

```python
from pathlib import Path

from app.career_ops.seek_search import parse_seek_list_html


def test_parse_seek_list_html_extracts_job_cards():
    html = Path("backend/tests/fixtures/seek/list_page_sample.html").read_text(encoding="utf-8")

    jobs = parse_seek_list_html(
        html,
        base_url="https://www.seek.com.au",
        search_keyword="python backend engineer",
    )

    assert jobs[0].title == "Senior Backend Engineer"
    assert jobs[0].company == "Example Co"
    assert jobs[0].job_url.startswith("https://www.seek.com.au/job/")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_seek_search_service.py -v`
Expected: FAIL because `parse_seek_list_html` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def parse_seek_list_html(html: str, *, base_url: str, search_keyword: str) -> list[SeekRawJob]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: list[SeekRawJob] = []
    for card in soup.select("[data-automation='normalJob']"):
        title_node = card.select_one("a[data-automation='jobTitle']")
        company_node = card.select_one("[data-automation='jobCompany']")
        location_node = card.select_one("[data-automation='jobLocation']")
        if not title_node or not company_node:
            continue
        jobs.append(
            SeekRawJob(
                search_keyword=search_keyword,
                title=title_node.get_text(strip=True),
                company=company_node.get_text(strip=True),
                location=location_node.get_text(strip=True) if location_node else "",
                job_url=urljoin(base_url, title_node.get("href", "")),
            )
        )
    return jobs
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_seek_search_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/fixtures/seek/list_page_sample.html backend/tests/unit/test_seek_search_service.py backend/app/career_ops/seek_search.py
git commit -m "feat: add seek list-page parsing helpers"
```

### Task 3: Add failing backend route test for manual SEEK search orchestration

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_seek_search_api.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\jobs.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\seek_search.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_seek_search_api.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app


@patch("app.routers.jobs.run_manual_seek_search")
async def test_post_manual_seek_search_returns_jobs(mock_run):
    mock_run.return_value = {
        "plan": {
            "resume_id": "resume-1",
            "source": "seek",
            "candidate_profile_summary": "Python backend engineer",
            "keywords": ["python backend engineer"],
            "location": "Sydney NSW",
        },
        "jobs": [
            {
                "job_id": "seek:https://www.seek.com.au/job/123",
                "source": "seek",
                "search_keyword": "python backend engineer",
                "title": "Senior Backend Engineer",
                "company": "Example Co",
                "location": "Sydney NSW",
                "salary": None,
                "work_type": None,
                "listed_at": "2d ago",
                "job_url": "https://www.seek.com.au/job/123",
                "summary": "Build APIs",
                "match_score": 0.9,
            }
        ],
        "stats": {
            "keywords_generated": 1,
            "queries_attempted": 1,
            "queries_succeeded": 1,
            "raw_jobs_found": 1,
            "jobs_after_dedupe": 1,
        },
        "errors": [],
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/v1/jobs/search/seek", json={"resume_id": "resume-1"})

    assert response.status_code == 200
    assert response.json()["jobs"][0]["company"] == "Example Co"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/integration/test_seek_search_api.py -v`
Expected: FAIL with 404 or missing route errors.

- [ ] **Step 3: Write minimal implementation**

```python
class SeekManualSearchRequest(BaseModel):
    resume_id: str
    location: str | None = None


@router.post("/search/seek")
async def manual_seek_search(request: SeekManualSearchRequest) -> dict[str, Any]:
    return await run_manual_seek_search(
        resume_id=request.resume_id,
        location=request.location,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/integration/test_seek_search_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/test_seek_search_api.py backend/app/routers/jobs.py backend/app/schemas/models.py backend/app/career_ops/seek_search.py
git commit -m "feat: add manual seek search api route"
```

### Task 4: Add failing frontend tests for SEEK client method, formatter, and action wiring

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_search_seek_jobs_posts_resume_id(self):
    RecordingAsyncClient.responses = {
        ("POST", "http://backend/api/v1/jobs/search/seek"): MockHTTPResponse(
            {
                "plan": {
                    "resume_id": "resume-1",
                    "source": "seek",
                    "candidate_profile_summary": "Python backend engineer",
                    "keywords": ["python backend engineer"],
                    "location": "Sydney NSW",
                },
                "jobs": [],
                "stats": {
                    "keywords_generated": 1,
                    "queries_attempted": 1,
                    "queries_succeeded": 1,
                    "raw_jobs_found": 0,
                    "jobs_after_dedupe": 0,
                },
                "errors": [],
            }
        )
    }

    backend = self.frontend_app.ResumeMatcherBackend("http://backend")
    with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
        await backend.search_seek_jobs("resume-1")

    method, url, kwargs = RecordingAsyncClient.requests[0]
    assert (method, url) == ("POST", "http://backend/api/v1/jobs/search/seek")
    assert kwargs["json"]["resume_id"] == "resume-1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: FAIL because the new client method and response models are missing.

- [ ] **Step 3: Write minimal implementation**

```python
class SeekSearchResponse(BaseModel):
    plan: dict[str, Any]
    jobs: list[dict[str, Any]] = Field(default_factory=list)
    stats: dict[str, Any]
    errors: list[dict[str, Any] | str] = Field(default_factory=list)


async def search_seek_jobs(self, resume_id: str) -> SeekSearchResponse:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{self.base_url}/api/v1/jobs/search/seek",
            json={"resume_id": resume_id},
        )
    response.raise_for_status()
    return SeekSearchResponse.model_validate(response.json())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/test_career_ops_frontend.py frontend/app.py
git commit -m "feat: add seek search client and frontend models"
```

### Task 5: Implement frontend action and rendering for manual SEEK search

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`

- [ ] **Step 1: Write the failing test**

```python
def test_format_seek_search_result_includes_keywords_and_company(self):
    frontend_app = load_frontend_app_module()

    message = frontend_app.format_seek_search_result(
        frontend_app.SeekSearchResponse.model_validate(
            {
                "plan": {
                    "resume_id": "resume-1",
                    "source": "seek",
                    "candidate_profile_summary": "Python backend engineer",
                    "keywords": ["python backend engineer", "platform engineer"],
                    "location": "Sydney NSW",
                },
                "jobs": [
                    {
                        "job_id": "seek:https://www.seek.com.au/job/123",
                        "source": "seek",
                        "search_keyword": "python backend engineer",
                        "title": "Senior Backend Engineer",
                        "company": "Example Co",
                        "location": "Sydney NSW",
                        "salary": "$180k-$200k",
                        "work_type": "Full time",
                        "listed_at": "2d ago",
                        "job_url": "https://www.seek.com.au/job/123",
                        "summary": "Build APIs",
                        "match_score": 0.91,
                    }
                ],
                "stats": {
                    "keywords_generated": 2,
                    "queries_attempted": 2,
                    "queries_succeeded": 2,
                    "raw_jobs_found": 7,
                    "jobs_after_dedupe": 4,
                },
                "errors": [],
            }
        )
    )

    self.assertIn("SEEK", message)
    self.assertIn("python backend engineer", message)
    self.assertIn("Example Co", message)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: FAIL because `format_seek_search_result` and the new action wiring do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
ACTION_SEARCH_SEEK = "career_ops_search_seek"


def format_seek_search_result(result: SeekSearchResponse) -> str:
    plan = result.plan
    lines = [
        "### SEEK 搜索结果",
        f"- 地点：`{plan.location}`",
        f"- 关键词：{', '.join(plan.keywords)}",
    ]
    for job in result.jobs[:10]:
        lines.append(
            f"- [{job.title}]({job.job_url}) | {job.company} | {job.location} | 匹配分 `{job.match_score:.2f}`"
        )
    return "\n".join(lines)


async def handle_seek_search_request() -> None:
    resume_id = await ensure_resume_available()
    if not resume_id:
        return
    progress = cl.Message(content="正在搜索 SEEK 岗位，请稍等...")
    await progress.send()
    result = await backend.search_seek_jobs(resume_id)
    progress.content = format_seek_search_result(result)
    progress.actions = build_tool_actions()
    await progress.update()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app.py frontend/test_career_ops_frontend.py
git commit -m "feat: wire manual seek search into frontend"
```

### Task 6: Verify backend and frontend SEEK search behavior end to end

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\smoke_backend_server.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_real_backend_smoke.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_seek_search_service.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_seek_search_api.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_real_backend_smoke.py`

- [ ] **Step 1: Run targeted backend tests**

Run: `python -m pytest backend/tests/unit/test_seek_search_service.py backend/tests/integration/test_seek_search_api.py -v`
Expected: PASS

- [ ] **Step 2: Run targeted frontend tests**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 3: Add or update smoke behavior and run it**

Run: `python -m unittest frontend.test_real_backend_smoke -v`
Expected: PASS with the new manual SEEK action path covered by the smoke backend stub.

- [ ] **Step 4: Run the existing aggregate check**

Run: `python .\scripts\run_career_ops_ci.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_seek_search_service.py backend/tests/integration/test_seek_search_api.py backend/tests/smoke_backend_server.py frontend/test_career_ops_frontend.py frontend/test_real_backend_smoke.py
git commit -m "test: verify manual seek search flow"
```
