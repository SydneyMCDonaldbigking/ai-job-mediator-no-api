# LangChain Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a minimal LangChain-backed AI task layer and migrate search query generation for SEEK and doda without changing frontend behavior or replacing the existing LiteLLM runtime.

**Architecture:** Keep `backend/app/llm.py` as the LiteLLM runtime gateway, add a new `backend/app/ai/` task layer, and move only search query generation into that new layer. Existing job search services continue to own scraper orchestration, response shaping, and scoring; they only swap their keyword-generation step to the new task entrypoint with a fallback path.

**Tech Stack:** FastAPI, LiteLLM, LangChain Core, Pydantic, Playwright, pytest

---

## File Map

### New files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\invoke.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\search_queries.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\search_queries.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_search_queries.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_search_queries_task.py`

### Modified files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\pyproject.toml`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\requirements.txt`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\seek_search.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\doda_search.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_seek_search_service.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_doda_search_service.py`

### Existing files to read first

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\llm.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\seek_search.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\doda_search.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`

## Task 1: Add Minimal LangChain Dependencies

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\pyproject.toml`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\requirements.txt`

- [ ] **Step 1: Verify the dependencies do not exist yet**

Run:

```powershell
rg -n "langchain-core|langchain" C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\pyproject.toml C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\requirements.txt
```

Expected: no matches.

- [ ] **Step 2: Add minimal dependencies to `pyproject.toml`**

Update the dependency list to include:

```toml
"langchain-core>=0.3.0,<0.4.0",
"langchain>=0.3.0,<0.4.0",
```

Place them directly after `"litellm==1.83.0",` so the AI runtime dependencies stay grouped.

- [ ] **Step 3: Mirror the same dependencies in `requirements.txt`**

Add:

```text
langchain-core>=0.3.0,<0.4.0
langchain>=0.3.0,<0.4.0
```

- [ ] **Step 4: Re-check both files**

Run:

```powershell
rg -n "langchain-core|langchain" C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\pyproject.toml C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\requirements.txt
```

Expected: both files show the two new entries.

- [ ] **Step 5: Commit**

```bash
git add backend/pyproject.toml backend/requirements.txt
git commit -m "chore: add minimal langchain dependencies"
```

## Task 2: Scaffold the AI Task Layer

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\__init__.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\__init__.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\__init__.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\__init__.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`

- [ ] **Step 1: Create package markers**

Contents:

```python
# backend/app/ai/__init__.py
"""AI task layer built on top of the existing LiteLLM runtime."""
```

```python
# backend/app/ai/core/__init__.py
"""Core runtime helpers for AI tasks."""
```

```python
# backend/app/ai/prompts/__init__.py
"""Prompt templates for AI tasks."""
```

```python
# backend/app/ai/parsers/__init__.py
"""Structured parsers for AI task outputs."""
```

```python
# backend/app/ai/tasks/__init__.py
"""Task entrypoints for LangChain-backed AI workflows."""
```

- [ ] **Step 2: Syntax check the new package files**

Run:

```powershell
python -m py_compile `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\__init__.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\__init__.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\__init__.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\__init__.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py
```

Expected: command exits successfully.

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai
git commit -m "chore: scaffold ai task layer packages"
```

## Task 3: Add Failing Search Query Parser Tests

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_search_queries_task.py`

- [ ] **Step 1: Write the failing parser tests**

Create the file with:

```python
from app.ai.parsers.search_queries import (
    SearchQueryTaskResult,
    normalize_search_query_task_result,
    parse_search_query_json,
)


def test_parse_search_query_json_accepts_expected_shape():
    payload = """
    {
      "candidate_profile_summary": "Backend engineer focused on Python APIs",
      "keywords": ["python backend engineer", "platform engineer"],
      "location": "Sydney NSW"
    }
    """

    result = parse_search_query_json(payload)

    assert result.candidate_profile_summary == "Backend engineer focused on Python APIs"
    assert result.keywords == ["python backend engineer", "platform engineer"]
    assert result.location == "Sydney NSW"


def test_normalize_search_query_task_result_dedupes_and_strips():
    raw = SearchQueryTaskResult(
        candidate_profile_summary="  Backend engineer  ",
        keywords=[" python backend engineer ", "platform engineer", "python backend engineer "],
        location=" Sydney NSW ",
    )

    normalized = normalize_search_query_task_result(raw)

    assert normalized.candidate_profile_summary == "Backend engineer"
    assert normalized.keywords == ["python backend engineer", "platform engineer"]
    assert normalized.location == "Sydney NSW"


def test_parse_search_query_json_rejects_empty_keywords():
    payload = """
    {
      "candidate_profile_summary": "Backend engineer",
      "keywords": [],
      "location": "Sydney NSW"
    }
    """

    try:
        parse_search_query_json(payload)
    except ValueError as exc:
        assert "keywords" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty keywords")
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend
python -m pytest tests/unit/test_generate_search_queries_task.py -v
```

Expected: FAIL with import errors because the parser module does not exist yet.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_generate_search_queries_task.py
git commit -m "test: add failing search query parser coverage"
```

## Task 4: Implement Search Query Parser and Prompt Builder

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\search_queries.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\search_queries.py`

- [ ] **Step 1: Implement `search_queries.py` parser**

Use:

```python
import json

from pydantic import BaseModel, Field


class SearchQueryTaskResult(BaseModel):
    candidate_profile_summary: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    location: str = Field(min_length=1)


def normalize_search_query_task_result(result: SearchQueryTaskResult) -> SearchQueryTaskResult:
    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in result.keywords:
        normalized = keyword.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    normalized_summary = result.candidate_profile_summary.strip()
    normalized_location = result.location.strip()

    if not deduped:
        raise ValueError("keywords cannot be empty")
    if not normalized_summary:
        raise ValueError("candidate_profile_summary cannot be empty")
    if not normalized_location:
        raise ValueError("location cannot be empty")

    return SearchQueryTaskResult(
        candidate_profile_summary=normalized_summary,
        keywords=deduped,
        location=normalized_location,
    )


def parse_search_query_json(payload: str) -> SearchQueryTaskResult:
    data = json.loads(payload)
    result = SearchQueryTaskResult.model_validate(data)
    return normalize_search_query_task_result(result)
```

- [ ] **Step 2: Implement `search_queries.py` prompt builder**

Use:

```python
from app.schemas.models import ResumeData


def build_search_query_prompt(*, resume: ResumeData, language: str, default_location: str) -> str:
    summary = resume.summary or "No summary provided."
    skills = ", ".join(resume.additional.technicalSkills[:12]) or "No technical skills listed."
    titles = ", ".join(entry.title for entry in resume.workExperience[:5] if entry.title) or "No recent titles listed."

    return f"""
You generate job search keywords for a candidate resume.

Return JSON only with this shape:
{{
  "candidate_profile_summary": "short summary",
  "keywords": ["keyword 1", "keyword 2"],
  "location": "{default_location}"
}}

Rules:
- Output 2 to 5 search keywords.
- Keep the keywords in {language}.
- Make them realistic job search phrases.
- Do not invent experience that is unsupported by the resume.
- Keep location as a plain string.

Resume summary:
{summary}

Recent titles:
{titles}

Skills:
{skills}
""".strip()
```

- [ ] **Step 3: Re-run the parser tests**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend
python -m pytest tests/unit/test_generate_search_queries_task.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/ai/parsers/search_queries.py backend/app/ai/prompts/search_queries.py
git commit -m "feat: add search query parser and prompt builder"
```

## Task 5: Add Failing Task Invocation Coverage

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_search_queries_task.py`

- [ ] **Step 1: Append the failing task test**

Add:

```python
from unittest.mock import AsyncMock, patch

from app.ai.tasks.generate_search_queries import generate_search_queries
from app.schemas.models import ResumeData


@patch("app.ai.tasks.generate_search_queries.invoke_json_task", new_callable=AsyncMock)
async def test_generate_search_queries_uses_invoke_helper(mock_invoke):
    mock_invoke.return_value = {
        "candidate_profile_summary": "Backend engineer",
        "keywords": ["python backend engineer", "platform engineer"],
        "location": "Sydney NSW",
    }

    resume = ResumeData.model_validate(
        {
            "summary": "Backend engineer working on Python APIs",
            "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
        }
    )

    result = await generate_search_queries(
        resume=resume,
        resume_id="resume-1",
        source="seek",
        language="en",
        default_location="Sydney NSW",
    )

    assert result.resume_id == "resume-1"
    assert result.source == "seek"
    assert result.keywords == ["python backend engineer", "platform engineer"]
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend
python -m pytest tests/unit/test_generate_search_queries_task.py -v
```

Expected: FAIL because `app.ai.tasks.generate_search_queries` does not exist yet.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/unit/test_generate_search_queries_task.py
git commit -m "test: add failing search query task coverage"
```

## Task 6: Implement the Runtime Helper and Search Query Task

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\invoke.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_search_queries.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`

- [ ] **Step 1: Implement the invoke helper**

Create:

```python
from typing import Any

from app.llm import complete


async def invoke_json_task(*, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    response = await complete(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
    )

    if not isinstance(response, dict):
        raise ValueError("Expected dict response from json task invocation")

    return response
```

If `complete(...)` does not exist with this exact signature, swap in the closest real JSON-capable helper from `backend/app/llm.py`, but keep the `invoke_json_task(...)` contract the same.

- [ ] **Step 2: Implement the search query task**

Create:

```python
from pydantic import BaseModel, Field

from app.ai.core.invoke import invoke_json_task
from app.ai.parsers.search_queries import SearchQueryTaskResult, normalize_search_query_task_result
from app.ai.prompts.search_queries import build_search_query_prompt
from app.schemas.models import ResumeData, SeekSearchPlan


class GeneratedSearchQueries(BaseModel):
    resume_id: str
    source: str
    candidate_profile_summary: str
    keywords: list[str] = Field(default_factory=list)
    location: str


def _fallback_keywords(*, resume: ResumeData, source: str) -> list[str]:
    text = " ".join(
        part
        for part in [
            resume.summary or "",
            *[entry.title for entry in resume.workExperience],
            *resume.additional.technicalSkills,
        ]
        if part
    ).lower()

    if source == "doda":
        if "backend" in text or "api" in text:
            return ["バックエンドエンジニア", "python エンジニア"]
        return ["ソフトウェアエンジニア"]

    if "python" in text and "backend" in text:
        return ["python backend engineer", "platform engineer"]
    if "api" in text:
        return ["backend api engineer"]
    return ["software engineer"]


async def generate_search_queries(
    *,
    resume: ResumeData,
    resume_id: str,
    source: str,
    language: str,
    default_location: str,
) -> GeneratedSearchQueries:
    prompt = build_search_query_prompt(
        resume=resume,
        language=language,
        default_location=default_location,
    )

    try:
        payload = await invoke_json_task(
            system_prompt="You generate structured job search queries. Return JSON only.",
            user_prompt=prompt,
        )
        parsed = normalize_search_query_task_result(SearchQueryTaskResult.model_validate(payload))
        keywords = parsed.keywords
        summary = parsed.candidate_profile_summary
        location = parsed.location
    except Exception:
        keywords = _fallback_keywords(resume=resume, source=source)
        summary = (resume.summary or "Candidate resume profile").strip()
        location = default_location.strip()

    return GeneratedSearchQueries(
        resume_id=resume_id,
        source=source,
        candidate_profile_summary=summary,
        keywords=keywords,
        location=location,
    )


def to_seek_search_plan(result: GeneratedSearchQueries) -> SeekSearchPlan:
    return SeekSearchPlan(
        resume_id=result.resume_id,
        source=result.source,
        candidate_profile_summary=result.candidate_profile_summary,
        keywords=result.keywords,
        location=result.location,
    )
```

- [ ] **Step 3: Export the task**

Set `backend/app/ai/tasks/__init__.py` to:

```python
"""Task entrypoints for LangChain-backed AI workflows."""

from app.ai.tasks.generate_search_queries import (
    GeneratedSearchQueries,
    generate_search_queries,
    to_seek_search_plan,
)

__all__ = ["GeneratedSearchQueries", "generate_search_queries", "to_seek_search_plan"]
```

- [ ] **Step 4: Add the fallback test**

Append to `backend/tests/unit/test_generate_search_queries_task.py`:

```python
@patch("app.ai.tasks.generate_search_queries.invoke_json_task", new_callable=AsyncMock)
async def test_generate_search_queries_falls_back_on_invoke_error(mock_invoke):
    mock_invoke.side_effect = RuntimeError("provider unavailable")

    resume = ResumeData.model_validate(
        {
            "summary": "Python backend engineer building APIs",
            "additional": {"technicalSkills": ["Python", "FastAPI"]},
        }
    )

    result = await generate_search_queries(
        resume=resume,
        resume_id="resume-2",
        source="seek",
        language="en",
        default_location="Sydney NSW",
    )

    assert result.keywords
    assert result.location == "Sydney NSW"
```

- [ ] **Step 5: Run the task tests**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend
python -m pytest tests/unit/test_generate_search_queries_task.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ai/core/invoke.py backend/app/ai/tasks/__init__.py backend/app/ai/tasks/generate_search_queries.py backend/tests/unit/test_generate_search_queries_task.py
git commit -m "feat: add search query ai task and runtime helper"
```

## Task 7: Wire SEEK Search to the New Task Layer

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\seek_search.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_seek_search_service.py`

- [ ] **Step 1: Replace the plan builder with a task-backed async builder**

Update `seek_search.py` so it has this structure:

```python
from app.ai.tasks import generate_search_queries, to_seek_search_plan


def _build_seek_search_plan_fallback(
    resume: ResumeData,
    *,
    resume_id: str,
    location: str = DEFAULT_SEEK_LOCATION,
) -> SeekSearchPlan:
    text = _resume_text(resume)
    keywords: list[str] = []

    if "python" in text and "backend" in text:
        keywords.append("python backend engineer")
    if "platform" in text or "aws" in text:
        keywords.append("platform engineer")
    if "fastapi" in text or "api" in text:
        keywords.append("backend api engineer")
    if not keywords:
        keywords.append("software engineer")

    profile_summary = resume.summary or "Candidate resume profile"
    return SeekSearchPlan(
        resume_id=resume_id,
        candidate_profile_summary=profile_summary,
        keywords=list(dict.fromkeys(keywords)),
        location=location,
    )


async def build_seek_search_plan(
    resume: ResumeData,
    *,
    resume_id: str,
    location: str = DEFAULT_SEEK_LOCATION,
) -> SeekSearchPlan:
    try:
        result = await generate_search_queries(
            resume=resume,
            resume_id=resume_id,
            source="seek",
            language="en",
            default_location=location,
        )
        return to_seek_search_plan(result)
    except Exception:
        return _build_seek_search_plan_fallback(
            resume,
            resume_id=resume_id,
            location=location,
        )
```

Then update `run_manual_seek_search(...)` to call:

```python
plan = await build_seek_search_plan(
    resume,
    resume_id=resume_id,
    location=location or DEFAULT_SEEK_LOCATION,
)
```

- [ ] **Step 2: Update the SEEK unit test**

Replace the current plan test with:

```python
from unittest.mock import AsyncMock, patch

from app.ai.tasks.generate_search_queries import GeneratedSearchQueries
from app.career_ops.seek_search import build_seek_search_plan
from app.schemas.models import ResumeData


@patch("app.career_ops.seek_search.generate_search_queries", new_callable=AsyncMock)
async def test_build_seek_search_plan_uses_ai_task(mock_generate):
    mock_generate.return_value = GeneratedSearchQueries(
        resume_id="resume-1",
        source="seek",
        candidate_profile_summary="Python backend engineer",
        keywords=["python backend engineer", "platform engineer"],
        location="Sydney NSW",
    )

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

    plan = await build_seek_search_plan(
        resume,
        resume_id="resume-1",
        location="Sydney NSW",
    )

    assert plan.keywords == ["python backend engineer", "platform engineer"]
    assert plan.source == "seek"
```

Keep the dedupe, scoring, and HTML parsing tests unchanged.

- [ ] **Step 3: Run the SEEK unit tests**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend
python -m pytest tests/unit/test_seek_search_service.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/career_ops/seek_search.py backend/tests/unit/test_seek_search_service.py
git commit -m "feat: wire seek query generation through ai task layer"
```

## Task 8: Wire doda Search to the New Task Layer

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\doda_search.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_doda_search_service.py`

- [ ] **Step 1: Replace the plan builder with a task-backed async builder**

Update `doda_search.py` so it has this structure:

```python
from app.ai.tasks import generate_search_queries, to_seek_search_plan


def _build_doda_search_plan_fallback(
    resume: ResumeData,
    *,
    resume_id: str,
    country: str = "JP",
    location_text: str = DEFAULT_DODA_LOCATION,
) -> SeekSearchPlan:
    text = _resume_text(resume)
    keywords: list[str] = []

    if "backend" in text or "api" in text:
        keywords.append("バックエンドエンジニア")
    if "python" in text:
        keywords.append("python エンジニア")
    if "aws" in text or "platform" in text:
        keywords.append("プラットフォームエンジニア")
    if "fastapi" in text:
        keywords.append("python バックエンド")
    if not keywords:
        keywords.append("ソフトウェアエンジニア")

    return SeekSearchPlan(
        resume_id=resume_id,
        source="doda",
        candidate_profile_summary=resume.summary or "Japanese candidate resume profile",
        keywords=list(dict.fromkeys(keywords)),
        location=localize_location_for_doda(country=country, location_text=location_text),
    )


async def build_doda_search_plan(
    resume: ResumeData,
    *,
    resume_id: str,
    country: str = "JP",
    location_text: str = DEFAULT_DODA_LOCATION,
) -> SeekSearchPlan:
    localized = localize_location_for_doda(country=country, location_text=location_text)
    try:
        result = await generate_search_queries(
            resume=resume,
            resume_id=resume_id,
            source="doda",
            language="ja",
            default_location=localized,
        )
        return to_seek_search_plan(result)
    except Exception:
        return _build_doda_search_plan_fallback(
            resume,
            resume_id=resume_id,
            country=country,
            location_text=location_text,
        )
```

Then update `run_manual_doda_search(...)` to call:

```python
plan = await build_doda_search_plan(
    resume,
    resume_id=resume_id,
    location_text=location or DEFAULT_DODA_LOCATION,
)
```

- [ ] **Step 2: Update the doda unit test**

Use:

```python
from unittest.mock import AsyncMock, patch

from app.ai.tasks.generate_search_queries import GeneratedSearchQueries
from app.career_ops.doda_search import build_doda_search_plan
from app.schemas.models import ResumeData


@patch("app.career_ops.doda_search.generate_search_queries", new_callable=AsyncMock)
async def test_build_doda_search_plan_uses_ai_task(mock_generate):
    mock_generate.return_value = GeneratedSearchQueries(
        resume_id="resume-ja-1",
        source="doda",
        candidate_profile_summary="日本語バックエンド候補者",
        keywords=["バックエンドエンジニア", "python エンジニア"],
        location="東京",
    )

    resume = ResumeData.model_validate(
        {
            "summary": "PythonとFastAPIでAPIを構築するバックエンドエンジニア。",
            "workExperience": [
                {
                    "id": 1,
                    "title": "バックエンドエンジニア",
                    "company": "Acme",
                    "years": "2022-現在",
                    "description": ["API開発", "AWS運用改善"],
                }
            ],
            "additional": {"technicalSkills": ["Python", "FastAPI", "AWS"]},
        }
    )

    plan = await build_doda_search_plan(
        resume,
        resume_id="resume-ja-1",
        country="JP",
        location_text="Tokyo",
    )

    assert plan.source == "doda"
    assert plan.keywords == ["バックエンドエンジニア", "python エンジニア"]
```

Keep the parser and normalization tests unchanged.

- [ ] **Step 3: Run the doda unit tests**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend
python -m pytest tests/unit/test_doda_search_service.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/career_ops/doda_search.py backend/tests/unit/test_doda_search_service.py
git commit -m "feat: wire doda query generation through ai task layer"
```

## Task 9: Run Integration and Regression Verification

**Files:**
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_search_queries_task.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_seek_search_service.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_doda_search_service.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_seek_search_api.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_doda_search_api.py`

- [ ] **Step 1: Run the focused backend test set**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend
python -m pytest `
  tests/unit/test_generate_search_queries_task.py `
  tests/unit/test_seek_search_service.py `
  tests/unit/test_doda_search_service.py `
  tests/integration/test_seek_search_api.py `
  tests/integration/test_doda_search_api.py -v
```

Expected: PASS.

- [ ] **Step 2: Run project-level regression validation**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator
python .\scripts\run_career_ops_ci.py
```

Expected: PASS, with no regression in SEEK or doda flows.

- [ ] **Step 3: Commit**

```bash
git add backend/app/ai backend/app/career_ops/seek_search.py backend/app/career_ops/doda_search.py backend/tests/unit/test_generate_search_queries_task.py backend/tests/unit/test_seek_search_service.py backend/tests/unit/test_doda_search_service.py backend/pyproject.toml backend/requirements.txt
git commit -m "feat: introduce langchain-backed search query task layer"
```

## Task 10: Align the Runtime Helper If `llm.py` Uses a Different JSON API

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\invoke.py`
- Read: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\llm.py`

- [ ] **Step 1: Inspect the real JSON-capable helper in `llm.py`**

Run:

```powershell
rg -n "json_mode|async def .*json|complete\\(|acompletion\\(" C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\llm.py
```

Expected: identify the exact helper that should back `invoke_json_task(...)`.

- [ ] **Step 2: If necessary, narrow `invoke_json_task(...)` to the real runtime signature**

Use this target shape if you need to adjust it:

```python
async def invoke_json_task(*, system_prompt: str, user_prompt: str) -> dict[str, Any]:
    payload = await complete_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    if not isinstance(payload, dict):
        raise ValueError("Expected dict payload from complete_json")
    return payload
```

Only do this task if the initial implementation in Task 6 does not align cleanly with the real `llm.py` API.

- [ ] **Step 3: Re-run the focused backend tests**

Run:

```powershell
cd C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend
python -m pytest `
  tests/unit/test_generate_search_queries_task.py `
  tests/unit/test_seek_search_service.py `
  tests/unit/test_doda_search_service.py `
  tests/integration/test_seek_search_api.py `
  tests/integration/test_doda_search_api.py -v
```

Expected: PASS.

## Self-Review Checklist

- Spec coverage:
  - AI task layer added: covered by Tasks 2, 4, 6
  - LiteLLM retained as runtime: covered by Tasks 6 and 10
  - Only `generate_search_queries` migrated: covered by Tasks 6, 7, 8
  - SEEK/doda compatibility preserved: covered by Tasks 7, 8, 9
  - Minimal dependency set: covered by Task 1
- Placeholder scan:
  - No `TODO`, `TBD`, `FIXME`, or `...` placeholders remain
- Type consistency:
  - `GeneratedSearchQueries` feeds `SeekSearchPlan`
  - service layer still consumes `SeekSearchPlan`
  - one task contract serves both SEEK and doda
