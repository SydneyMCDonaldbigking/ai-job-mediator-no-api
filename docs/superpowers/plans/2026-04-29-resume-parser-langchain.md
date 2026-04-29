# Resume Parser LangChain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move structured resume parsing into the backend AI task layer while preserving markdown conversion, date restoration, final `ResumeData` validation, and stored resume shape.

**Architecture:** Keep `backend/app/services/parser.py` as the service entrypoint and move only the LLM-heavy structured extraction into a new `backend/app/ai/tasks/parse_resume.py` task backed by the existing LiteLLM JSON adapter pattern. Preserve service-layer date restoration and final schema validation.

**Tech Stack:** FastAPI, LiteLLM, langchain-core, Pydantic, pytest

---

## File Map

### New files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\parse_resume.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\parse_resume.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\parse_resume.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_parse_resume_task.py`

### Modified files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\parser.py`

### Existing files to read first

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\parser.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\prompts\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\prompts\templates.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\invoke.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`

## Task 1: Add the Resume Parse AI Task With Tests First

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\parse_resume.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\parsers\parse_resume.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\parse_resume.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_parse_resume_task.py`

- [ ] Write failing unit tests for:
  - runnable shape
  - structured JSON parsing into a typed task result
  - error propagation when the runnable fails
  - normalization of key task fields
- [ ] Implement a dedicated parse-resume prompt builder that reuses the existing parsing prompt and schema example.
- [ ] Implement a dedicated parse-resume parser that validates the JSON shape before service-level `ResumeData` validation.
- [ ] Implement the LangChain-core runnable task using the existing LiteLLM JSON invoke helper.
- [ ] Run the new task tests until they pass.

## Task 2: Rewire the Service Layer

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\parser.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_parse_resume_task.py`

- [ ] Add a lazy delegator in `parser.py` that imports the AI task at call time.
- [ ] Update `parse_resume_to_json(...)` to delegate to the new task while keeping its current signature and return type.
- [ ] Preserve the existing service-layer steps:
  - `restore_dates_from_markdown(...)`
  - final `ResumeData.model_validate(...)`
- [ ] Export the parse-resume task from `backend/app/ai/tasks/__init__.py`.
- [ ] Add a service-level delegation test that confirms date restoration still happens after task output.

## Task 3: Regression Verification

**Files:**
- No new production files expected

- [ ] Run focused pytest coverage for:
  - `backend/tests/unit/test_parse_resume_task.py`
  - `backend/tests/unit/test_generate_resume_title_task.py`
  - `backend/tests/unit/test_generate_outreach_message_task.py`
  - `backend/tests/unit/test_generate_cover_letter_task.py`
  - relevant parser/service integration tests if present
- [ ] Run `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\scripts\run_career_ops_ci.py`
- [ ] Confirm no upload/router/frontend contract changes are required.

## Risks And Guardrails

- Do not change markitdown conversion behavior.
- Do not move date restoration out of the service layer in this slice.
- Do not change the final `ResumeData` schema contract.
- Avoid touching frontend, scheduler, scraper, or PDF code.
- Keep unrelated working-tree changes out of the commit.

## Definition Of Done

- Structured resume parsing lives behind `backend/app/ai/tasks/parse_resume.py`.
- `backend/app/services/parser.py` delegates to the new task without changing callers.
- Date restoration and final `ResumeData` validation still apply exactly as before.
- Focused backend tests pass.
- Full career-ops CI passes.
- The change can be committed as one isolated LangChain slice.
