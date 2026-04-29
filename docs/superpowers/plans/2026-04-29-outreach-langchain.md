# Outreach Message LangChain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move outreach message generation into the backend AI task layer while preserving the current router behavior, stored resume shape, and plain-text output.

**Architecture:** Keep `backend/app/services/cover_letter.py` as the service entrypoint and move only the LLM-heavy outreach generation into a new `backend/app/ai/tasks/generate_outreach_message.py` task backed by the existing LiteLLM gateway through the LangChain-core adapter pattern. Do not migrate resume title generation in this slice.

**Tech Stack:** FastAPI, LiteLLM, langchain-core, Pydantic, pytest

---

## File Map

### New files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\generate_outreach_message.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_outreach_message.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_outreach_message_task.py`

### Modified files

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py`

### Existing files to read first

- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\prompts\templates.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\core\invoke.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_cover_letter.py`
- `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\resumes.py`

## Task 1: Add the Outreach AI Task With Tests First

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\prompts\generate_outreach_message.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\generate_outreach_message.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_outreach_message_task.py`

- [ ] Write failing unit tests for the runnable shape, text normalization, and error propagation.
- [ ] Implement the prompt builder by reusing `OUTREACH_MESSAGE_PROMPT` and existing language-name helpers.
- [ ] Implement the LangChain-core runnable task with the existing LiteLLM text invoke helper.
- [ ] Run the new task tests until they pass.

## Task 2: Rewire the Service Layer

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\ai\tasks\__init__.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_generate_outreach_message_task.py`

- [ ] Add a lazy delegator in `cover_letter.py` that imports the AI task at call time.
- [ ] Update `generate_outreach_message(...)` to delegate to the new task while keeping its current signature and return type.
- [ ] Export the outreach task from `backend/app/ai/tasks/__init__.py`.
- [ ] Add a service-level delegation test so the seam matches the cover-letter migration pattern.

## Task 3: Regression Verification

**Files:**
- No new production files expected

- [ ] Run focused pytest coverage for:
  - `backend/tests/unit/test_generate_outreach_message_task.py`
  - `backend/tests/unit/test_generate_cover_letter_task.py`
  - `backend/tests/unit/test_evaluate_job_task.py`
  - `backend/tests/integration/test_career_ops_api.py`
- [ ] Run `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\scripts\run_career_ops_ci.py`
- [ ] Confirm no router/API/frontend contract changes are required.

## Risks And Guardrails

- Do not migrate `generate_resume_title(...)` in this slice.
- Do not change prompt wording rules beyond moving them behind the AI task boundary.
- Preserve plain-text output semantics exactly.
- Avoid touching frontend, scheduler, or scraper code.
- Keep unrelated working-tree changes out of the commit.

## Definition Of Done

- Outreach generation lives behind `backend/app/ai/tasks/generate_outreach_message.py`.
- `backend/app/services/cover_letter.py` delegates to the new task without changing callers.
- Focused backend tests pass.
- Full career-ops CI passes.
- The change can be committed as one isolated LangChain slice.
