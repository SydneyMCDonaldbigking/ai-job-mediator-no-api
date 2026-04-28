# Job Evaluation LangChain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract the LLM-heavy portion of job evaluation into the backend AI task layer while preserving the existing `/api/evaluate-job` behavior and `CareerOpsEvaluationData` output shape.

**Architecture:** Keep `backend/app/career_ops/evaluator.py` as the product service that prepares resume/JD context, builds heuristic fallbacks, applies market signals, and assembles the final response. Add a new LangChain-backed AI task under `backend/app/ai/` that owns the evaluation prompt, structured parsing, and runnable-based LiteLLM invocation.

**Tech Stack:** FastAPI, LiteLLM, langchain-core, Pydantic, pytest, unittest

---

## File Map

### New files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\evaluate_job.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\evaluate_job.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\evaluate_job.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_evaluate_job_task.py`

### Modified files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\evaluator.py`

### Existing files to read first

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\evaluator.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\invoke.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_search_queries.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_career_ops_api.py`

## Task 1: Add Evaluation Parser and Task Tests First

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\evaluate_job.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\evaluate_job.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_evaluate_job_task.py`

- [ ] **Step 1: Write the failing parser and runnable tests**

Create `backend/tests/unit/test_evaluate_job_task.py` with tests that lock the minimum contract:

```python
import asyncio
import importlib

import pytest

from app.ai.parsers.evaluate_job import (
    EvaluationDimensionResult,
    EvaluationTaskResult,
    normalize_evaluation_task_result,
)
from app.ai.tasks.evaluate_job import (
    EvaluateJobRunnableInput,
    GeneratedJobEvaluation,
    build_evaluate_job_runnable,
    generate_job_evaluation,
)

evaluate_job_module = importlib.import_module("app.ai.tasks.evaluate_job")


def test_normalize_evaluation_task_result_preserves_all_blueprint_keys():
    raw = EvaluationTaskResult(
        executive_summary="Strong backend fit.",
        archetype="Backend platform engineer",
        overall_label="strong fit",
        dimensions=[
            EvaluationDimensionResult(
                key="archetype_fit",
                category="A",
                label="Archetype Fit",
                score=4.2,
                rationale="Clear backend alignment.",
                evidence=["Backend API experience"],
                risks=["Limited domain context"],
            ),
        ],
        tailoring_priorities=["Highlight API scale"],
        interview_focus=["STAR story about platform work"],
        keyword_targets=["Python", "FastAPI"],
    )

    normalized = normalize_evaluation_task_result(raw)

    assert normalized.executive_summary == "Strong backend fit."
    assert normalized.archetype == "Backend platform engineer"
    assert normalized.dimensions[0].key == "archetype_fit"
    assert normalized.keyword_targets == ["Python", "FastAPI"]


def test_generate_job_evaluation_uses_langchain_runnable(monkeypatch: pytest.MonkeyPatch):
    class FakeRunnable:
        async def ainvoke(self, task_input: EvaluateJobRunnableInput) -> dict[str, object]:
            assert "Backend Engineer" in task_input.resume_text
            assert "FastAPI" in task_input.job_description
            return {
                "executive_summary": "Strong backend fit.",
                "archetype": "Backend platform engineer",
                "overall_label": "strong fit",
                "dimensions": [
                    {
                        "key": "archetype_fit",
                        "category": "A",
                        "label": "Archetype Fit",
                        "score": 4.2,
                        "rationale": "Clear backend alignment.",
                        "evidence": ["Backend API experience"],
                        "risks": ["Limited domain context"],
                    }
                ],
                "tailoring_priorities": ["Highlight API scale"],
                "interview_focus": ["STAR story about platform work"],
                "keyword_targets": ["Python", "FastAPI"],
            }

    monkeypatch.setattr(
        evaluate_job_module,
        "build_evaluate_job_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_job_evaluation(
            resume_text="Backend Engineer with Python and AWS",
            job_description="Senior FastAPI engineer role",
            keyword_targets=["Python", "FastAPI"],
            market_context="Salary signals available",
        )
    )

    assert isinstance(result, GeneratedJobEvaluation)
    assert result.executive_summary == "Strong backend fit."
    assert result.dimensions[0].key == "archetype_fit"


def test_generate_job_evaluation_surfaces_schema_failures_after_successful_invoke(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: EvaluateJobRunnableInput) -> dict[str, object]:
            return {
                "executive_summary": "Strong backend fit.",
                "archetype": "Backend platform engineer",
                "overall_label": "strong fit",
                "dimensions": [],
                "tailoring_priorities": [],
                "interview_focus": [],
                "keyword_targets": [],
            }

    monkeypatch.setattr(
        evaluate_job_module,
        "build_evaluate_job_runnable",
        lambda: FakeRunnable(),
    )

    with pytest.raises(ValueError):
        asyncio.run(
            generate_job_evaluation(
                resume_text="Backend Engineer with Python and AWS",
                job_description="Senior FastAPI engineer role",
                keyword_targets=["Python", "FastAPI"],
                market_context="Salary signals available",
            )
        )
```

- [ ] **Step 2: Run the new test file and confirm it fails**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_evaluate_job_task.py -v
```

Expected: import failure for missing parser/task modules.

- [ ] **Step 3: Implement the prompt, parser, and task modules minimally**

Create `backend/app/ai/prompts/evaluate_job.py` with a `PromptTemplate` and helper:

```python
from langchain_core.prompts import PromptTemplate

EVALUATE_JOB_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """
You are evaluating a job application using a structured A-F job search framework.

Return JSON only with this shape:
{{
  "executive_summary": "short paragraph",
  "archetype": "short archetype label",
  "overall_label": "weak fit | mixed fit | strong fit",
  "dimensions": [
    {{
      "key": "archetype_fit",
      "category": "A",
      "label": "Archetype Fit",
      "score": 0.0,
      "rationale": "why",
      "evidence": ["resume proof point 1"],
      "risks": ["risk or gap"]
    }}
  ],
  "tailoring_priorities": ["priority 1"],
  "interview_focus": ["story 1"],
  "keyword_targets": ["keyword 1"]
}}

Use exactly these dimension definitions:
{dimension_lines}

Resume:
{resume_text}

Job Description:
{job_description}

Keyword Targets:
{keyword_targets}

Market Context:
{market_context}
""".strip()
)
```

Create `backend/app/ai/parsers/evaluate_job.py` with:

```python
from pydantic import BaseModel, Field


class EvaluationDimensionResult(BaseModel):
    key: str = Field(min_length=1)
    category: str = Field(min_length=1)
    label: str = Field(min_length=1)
    score: float
    rationale: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class EvaluationTaskResult(BaseModel):
    executive_summary: str = Field(min_length=1)
    archetype: str = Field(min_length=1)
    overall_label: str = Field(min_length=1)
    dimensions: list[EvaluationDimensionResult] = Field(min_length=1)
    tailoring_priorities: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    keyword_targets: list[str] = Field(default_factory=list)


def normalize_evaluation_task_result(result: EvaluationTaskResult) -> EvaluationTaskResult:
    dimensions = [
        EvaluationDimensionResult(
            key=item.key.strip(),
            category=item.category.strip().upper(),
            label=item.label.strip(),
            score=float(item.score),
            rationale=item.rationale.strip(),
            evidence=[entry.strip() for entry in item.evidence if entry.strip()],
            risks=[entry.strip() for entry in item.risks if entry.strip()],
        )
        for item in result.dimensions
    ]
    if not dimensions:
        raise ValueError("dimensions must contain at least one scored dimension")
    return EvaluationTaskResult(
        executive_summary=result.executive_summary.strip(),
        archetype=result.archetype.strip(),
        overall_label=result.overall_label.strip(),
        dimensions=dimensions,
        tailoring_priorities=[entry.strip() for entry in result.tailoring_priorities if entry.strip()],
        interview_focus=[entry.strip() for entry in result.interview_focus if entry.strip()],
        keyword_targets=[entry.strip() for entry in result.keyword_targets if entry.strip()],
    )
```

Create `backend/app/ai/tasks/evaluate_job.py` with:

```python
from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from app.ai.core.invoke import build_litellm_json_runnable
from app.ai.parsers.evaluate_job import EvaluationTaskResult, normalize_evaluation_task_result
from app.ai.prompts.evaluate_job import EVALUATE_JOB_PROMPT_TEMPLATE

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = object


class EvaluateJobRunnableInput(BaseModel):
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    keyword_targets: list[str] = Field(default_factory=list)
    market_context: str = Field(min_length=1)
    dimension_lines: str = Field(min_length=1)
    config: LLMConfig | None = None
    max_tokens: int = 2400
    retries: int = 2


class GeneratedJobEvaluation(EvaluationTaskResult):
    pass


def _build_payload(task_input: EvaluateJobRunnableInput) -> dict[str, object]:
    prompt = EVALUATE_JOB_PROMPT_TEMPLATE.format(
        resume_text=task_input.resume_text,
        job_description=task_input.job_description,
        keyword_targets=", ".join(task_input.keyword_targets) or "None",
        market_context=task_input.market_context,
        dimension_lines=task_input.dimension_lines,
    )
    return {
        "prompt": prompt,
        "system_prompt": "You are a truthful job-search strategist. Never invent compensation facts or experience not present in the resume.",
        "config": task_input.config,
        "max_tokens": task_input.max_tokens,
        "retries": task_input.retries,
    }


def build_evaluate_job_runnable() -> RunnableSerializable[EvaluateJobRunnableInput, dict[str, object]]:
    return RunnableLambda(_build_payload) | build_litellm_json_runnable()


async def generate_job_evaluation(**kwargs) -> GeneratedJobEvaluation:
    task_input = EvaluateJobRunnableInput(**kwargs)
    raw = await build_evaluate_job_runnable().ainvoke(task_input)
    parsed = EvaluationTaskResult.model_validate(raw)
    normalized = normalize_evaluation_task_result(parsed)
    return GeneratedJobEvaluation(**normalized.model_dump())
```

- [ ] **Step 4: Run the task tests and make them pass**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_evaluate_job_task.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the isolated AI task slice**

```bash
git add backend/app/ai/prompts/evaluate_job.py backend/app/ai/parsers/evaluate_job.py backend/app/ai/tasks/evaluate_job.py backend/tests/unit/test_evaluate_job_task.py
git commit -m "feat: add langchain job evaluation task"
```

## Task 2: Rewire `evaluate_job_fit(...)` To Use The New Task

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\evaluator.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`

- [ ] **Step 1: Add a failing service-level test for delegation**

Append to `backend/tests/unit/test_evaluate_job_task.py`:

```python
from app.career_ops import evaluator as evaluator_module
from app.schemas.models import CareerOpsMarketData


def test_evaluate_job_fit_delegates_to_ai_task_and_preserves_output_shape(monkeypatch: pytest.MonkeyPatch):
    async def fake_generate_job_evaluation(**kwargs):
        return GeneratedJobEvaluation(
            executive_summary="Strong backend fit.",
            archetype="Backend platform engineer",
            overall_label="strong fit",
            dimensions=[
                EvaluationDimensionResult(
                    key="archetype_fit",
                    category="A",
                    label="Archetype Fit",
                    score=4.2,
                    rationale="Clear backend alignment.",
                    evidence=["Backend API experience"],
                    risks=["Limited domain context"],
                )
            ],
            tailoring_priorities=["Highlight API scale"],
            interview_focus=["STAR story about platform work"],
            keyword_targets=["Python", "FastAPI"],
        )

    async def fake_market_signals(*args, **kwargs):
        return CareerOpsMarketData(
            compensation_summary="Salary range seen.",
            demand_summary="Demand looks healthy.",
            salary_mentions=["180k base"],
            market_notes=["Strong backend demand"],
            sources=["seek"],
        )

    monkeypatch.setattr(evaluator_module, "generate_job_evaluation", fake_generate_job_evaluation)
    monkeypatch.setattr(evaluator_module, "fetch_market_signals", fake_market_signals)

    result = asyncio.run(
        evaluator_module.evaluate_job_fit(
            resume={"summary": "Backend engineer with FastAPI and AWS"},
            job_description="Senior FastAPI engineer role",
        )
    )

    assert result.executive_summary == "Strong backend fit."
    assert result.overall_label == "strong fit"
    assert result.dimensions
    assert result.market_data is not None
```

- [ ] **Step 2: Run the new service-level test and confirm it fails**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_evaluate_job_task.py::test_evaluate_job_fit_delegates_to_ai_task_and_preserves_output_shape -v
```

Expected: FAIL because `evaluator.py` does not import or call `generate_job_evaluation` yet.

- [ ] **Step 3: Wire the service to the new task**

Update `backend/app/ai/tasks/__init__.py` to export:

```python
from app.ai.tasks.evaluate_job import GeneratedJobEvaluation, generate_job_evaluation
```

Update `backend/app/career_ops/evaluator.py`:

- remove direct `from app.llm import complete_json`
- add `from app.ai.tasks import generate_job_evaluation`
- keep `build_job_evaluation_prompt(...)` temporarily only if still needed elsewhere; otherwise remove it in this slice
- in `evaluate_job_fit(...)`, replace the direct `complete_json(...)` block with:

```python
    raw_result: dict[str, Any] = {}
    try:
        dimension_lines = "\n".join(
            f"- {item['category']}::{item['key']} — {item['label']}: {item['prompt_focus']}"
            for item in DEFAULT_DIMENSION_BLUEPRINT
        )
        generated = await generate_job_evaluation(
            resume_text=resume_to_text(resume_data),
            job_description=job_description,
            keyword_targets=keyword_targets,
            market_context="Market data will be applied after base evaluation.",
            dimension_lines=dimension_lines,
        )
        raw_result = generated.model_dump()
    except Exception as exc:
        logger.warning("Career Ops evaluator fell back to heuristic scoring: %s", exc)
```

Leave the existing fallback, `_normalize_dimension_payload(...)`, market enrichment, and final `CareerOpsEvaluationData(...)` assembly intact.

- [ ] **Step 4: Run the service-level test and nearby evaluation API test**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_evaluate_job_task.py C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_career_ops_api.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the evaluator integration**

```bash
git add backend/app/ai/tasks/__init__.py backend/app/career_ops/evaluator.py backend/tests/unit/test_evaluate_job_task.py
git commit -m "refactor: route job evaluation through ai task layer"
```

## Task 3: Full Regression Verification

**Files:**
- No new files
- Validate existing backend and career ops surfaces

- [ ] **Step 1: Run focused backend regression for both LangChain slices**

Run:

```powershell
D:\anaconda\envs\comp9321_py313\python.exe -m pytest `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_search_queries_task.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_evaluate_job_task.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_seek_search_service.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_doda_search_service.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_seek_search_api.py `
  C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_doda_search_api.py `
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

- [ ] **Step 3: Commit if verification required follow-up test fixes**

If any test-only fix was needed during regression:

```bash
git add backend/tests
git commit -m "test: stabilize job evaluation langchain regression coverage"
```

- [ ] **Step 4: Record final status**

Capture in the handoff:

- which files changed
- which commands passed
- whether any remaining work is purely future migration work

## Self-Review

- Spec coverage check: this plan covers the new prompt/parser/task files, evaluator rewiring, compatibility preservation, and regression verification.
- Placeholder scan: no `TODO/TBD/FIXME` steps remain.
- Type consistency: `EvaluateJobRunnableInput`, `GeneratedJobEvaluation`, and `generate_job_evaluation(...)` are defined once and reused consistently across tasks.
