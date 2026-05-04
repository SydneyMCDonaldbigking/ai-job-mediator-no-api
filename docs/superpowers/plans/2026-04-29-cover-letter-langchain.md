# Cover Letter LangChain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move cover letter generation into the backend AI task layer while preserving the current router behavior, stored resume shape, and plain-text output.

**Architecture:** Keep `backend/app/services/cover_letter.py` as the service entrypoint and move only the LLM-heavy cover letter generation into a new `backend/app/ai/tasks/generate_cover_letter.py` task backed by the existing LiteLLM gateway through the LangChain-core adapter pattern. Do not migrate outreach or title generation in this slice.

**Tech Stack:** FastAPI, LiteLLM, langchain-core, Pydantic, pytest

---

## File Map

### New files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\generate_cover_letter.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_cover_letter.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_cover_letter_task.py`

### Modified files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py`

### Existing files to read first

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\prompts\templates.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\invoke.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_search_queries.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\resumes.py`

## Task 1: Add the Cover Letter AI Task With Tests First

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\generate_cover_letter.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_cover_letter.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_cover_letter_task.py`

- [ ] **Step 1: Write the failing unit tests**

Create `backend/tests/unit/test_generate_cover_letter_task.py` with:

```python
import asyncio
import importlib

import pytest

from app.ai.tasks.generate_cover_letter import (
    CoverLetterRunnableInput,
    build_generate_cover_letter_runnable,
    generate_cover_letter_text,
)

cover_letter_task_module = importlib.import_module("app.ai.tasks.generate_cover_letter")


def test_build_generate_cover_letter_runnable_returns_ainvokable_pipeline():
    runnable = build_generate_cover_letter_runnable()
    assert hasattr(runnable, "ainvoke")


def test_generate_cover_letter_text_uses_langchain_runnable(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: CoverLetterRunnableInput) -> str:
            assert task_input.language == "en"
            assert "FastAPI" in task_input.job_description
            assert "Python" in str(task_input.resume_data)
            return "  Tailored cover letter body.  "

    monkeypatch.setattr(
        cover_letter_task_module,
        "build_generate_cover_letter_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_cover_letter_text(
            resume_data={"summary": "Python backend engineer", "skills": ["Python", "FastAPI"]},
            job_description="Senior FastAPI engineer role",
            language="en",
        )
    )

    assert result == "Tailored cover letter body."


def test_generate_cover_letter_text_propagates_task_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: CoverLetterRunnableInput) -> str:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        cover_letter_task_module,
        "build_generate_cover_letter_runnable",
        lambda: FakeRunnable(),
    )

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        asyncio.run(
            generate_cover_letter_text(
                resume_data={"summary": "Python backend engineer"},
                job_description="Senior FastAPI engineer role",
                language="en",
            )
        )
```

- [ ] **Step 2: Run the new tests and confirm they fail**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_cover_letter_task.py -v
```

Expected: import failure because the new prompt/task modules do not exist yet.

- [ ] **Step 3: Implement the prompt and task**

Create `backend/app/ai/prompts/generate_cover_letter.py` with:

```python
import json

from langchain_core.prompts import PromptTemplate

from app.prompts import get_language_name
from app.prompts.templates import COVER_LETTER_PROMPT


GENERATE_COVER_LETTER_PROMPT_TEMPLATE = PromptTemplate.from_template(
    COVER_LETTER_PROMPT.strip()
)


def build_generate_cover_letter_prompt(
    *,
    resume_data: dict,
    job_description: str,
    language: str,
) -> str:
    return GENERATE_COVER_LETTER_PROMPT_TEMPLATE.format(
        job_description=job_description,
        resume_data=json.dumps(resume_data, ensure_ascii=False),
        output_language=get_language_name(language),
    )
```

Create `backend/app/ai/tasks/generate_cover_letter.py` with:

```python
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from app.ai.core.invoke import invoke_text_task
from app.ai.prompts.generate_cover_letter import build_generate_cover_letter_prompt

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = object


class CoverLetterRunnableInput(BaseModel):
    resume_data: dict[str, Any]
    job_description: str = Field(min_length=1)
    language: str = Field(min_length=1)
    config: LLMConfig | None = None
    max_tokens: int = 2048


def _build_cover_letter_payload(task_input: CoverLetterRunnableInput) -> dict[str, object]:
    prompt = build_generate_cover_letter_prompt(
        resume_data=task_input.resume_data,
        job_description=task_input.job_description,
        language=task_input.language,
    )
    return {
        "prompt": prompt,
        "system_prompt": "You are a professional career coach and resume writer. Write compelling, personalized cover letters.",
        "config": task_input.config,
        "max_tokens": task_input.max_tokens,
    }


async def _invoke_cover_letter_payload(payload: dict[str, object]) -> str:
    return await invoke_text_task(
        prompt=payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        config=payload.get("config"),
        max_tokens=payload.get("max_tokens", 2048),
    )


def build_generate_cover_letter_runnable() -> RunnableSerializable[CoverLetterRunnableInput, str]:
    return RunnableLambda(_build_cover_letter_payload) | RunnableLambda(
        _invoke_cover_letter_payload
    )


async def generate_cover_letter_text(
    *,
    resume_data: dict[str, Any],
    job_description: str,
    language: str = "en",
    config: LLMConfig | None = None,
    max_tokens: int = 2048,
) -> str:
    task_input = CoverLetterRunnableInput(
        resume_data=resume_data,
        job_description=job_description,
        language=language,
        config=config,
        max_tokens=max_tokens,
    )
    result = await build_generate_cover_letter_runnable().ainvoke(task_input)
    return result.strip()
```

- [ ] **Step 4: Add any minimal missing text invoke helper**

If `backend/app/ai/core/invoke.py` does not yet expose a text-mode helper, add:

```python
async def invoke_text_task(
    prompt: str,
    system_prompt: str | None = None,
    config: LLMConfig | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    from app.llm import complete

    return await complete(
        prompt=prompt,
        system_prompt=system_prompt,
        config=config,
        max_tokens=max_tokens,
        temperature=temperature,
    )
```

Keep this as a minimal helper only. Do not alter the existing JSON helper behavior.

- [ ] **Step 5: Run the task tests and make them pass**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_cover_letter_task.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit the isolated cover letter task**

```bash
git add backend/app/ai/prompts/generate_cover_letter.py backend/app/ai/tasks/generate_cover_letter.py backend/app/ai/core/invoke.py backend/tests/unit/test_generate_cover_letter_task.py
git commit -m "feat: add langchain cover letter task"
```

## Task 2: Rewire the Existing Service To Use the AI Task

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_cover_letter_task.py`

- [ ] **Step 1: Add a failing delegation test for the service wrapper**

Append to `backend/tests/unit/test_generate_cover_letter_task.py`:

```python
from app.services import cover_letter as cover_letter_service_module


def test_generate_cover_letter_service_delegates_to_ai_task(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_generate_cover_letter_text(**kwargs) -> str:
        assert kwargs["language"] == "ja"
        assert "FastAPI" in kwargs["job_description"]
        return "Delegated cover letter"

    monkeypatch.setattr(
        cover_letter_service_module,
        "generate_cover_letter_text",
        fake_generate_cover_letter_text,
    )

    result = asyncio.run(
        cover_letter_service_module.generate_cover_letter(
            resume_data={"summary": "Python backend engineer"},
            job_description="Senior FastAPI engineer role",
            language="ja",
        )
    )

    assert result == "Delegated cover letter"
```

- [ ] **Step 2: Run the service-level test and confirm it fails**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_cover_letter_task.py::test_generate_cover_letter_service_delegates_to_ai_task -v
```

Expected: FAIL because the service still calls `complete(...)` directly.

- [ ] **Step 3: Export and wire the new task into the service**

Update `backend/app/ai/tasks/__init__.py` to export:

```python
from app.ai.tasks.generate_cover_letter import generate_cover_letter_text
```

Update `backend/app/services/cover_letter.py`:

- remove the direct `complete` dependency from `generate_cover_letter(...)`
- keep outreach and title generation unchanged
- add a lazy task wrapper:

```python
async def generate_cover_letter_text(**kwargs) -> str:
    from app.ai.tasks.generate_cover_letter import generate_cover_letter_text as task_impl

    return await task_impl(**kwargs)
```

- replace the direct prompt + `complete(...)` block inside `generate_cover_letter(...)` with:

```python
    return await generate_cover_letter_text(
        resume_data=resume_data,
        job_description=job_description,
        language=language,
    )
```

Do not change `generate_outreach_message(...)` or `generate_resume_title(...)` in this slice.

- [ ] **Step 4: Run the service-level test and nearby resume-related tests**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_cover_letter_task.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the service wiring**

```bash
git add backend/app/ai/tasks/__init__.py backend/app/services/cover_letter.py backend/tests/unit/test_generate_cover_letter_task.py
git commit -m "refactor: route cover letter generation through ai task layer"
```

## Task 3: Regression Verification

**Files:**
- No new files
- Validate existing backend behavior only

- [ ] **Step 1: Run focused backend regression for the new slice**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_cover_letter_task.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_search_queries_task.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_evaluate_job_task.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_career_ops_api.py -v
```

Expected: PASS.

- [ ] **Step 2: Run the full career ops CI**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\scripts\run_career_ops_ci.py
```

Expected:

```text
Career Ops CI checks completed successfully.
OK
```

- [ ] **Step 3: Commit only if test-only stabilization was needed**

If any additional test-only fix was required during verification:

```bash
git add backend/tests
git commit -m "test: stabilize cover letter langchain regression coverage"
```

- [ ] **Step 4: Record final handoff status**

Summarize:

- changed files
- commands that passed
- remaining future work (`outreach` and `resume title` still not migrated)

## Self-Review

- Spec coverage check: this plan covers the new prompt/task files, service rewiring, compatibility preservation, and regression verification.
- Placeholder scan: no `TODO/TBD/FIXME` plan steps remain.
- Type consistency: `CoverLetterRunnableInput`, `generate_cover_letter_text(...)`, and the service wrapper names are used consistently throughout the plan.
