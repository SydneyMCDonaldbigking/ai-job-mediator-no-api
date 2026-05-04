## Cover Letter LangChain Integration Design

Date: 2026-04-29  
Status: Proposed  
Scope: Backend AI task layer only

### Goal

Migrate cover letter generation into the backend AI task layer without changing the current API behavior, resume router flow, storage shape, or LiteLLM runtime gateway.

This is the third LangChain migration slice after:

- search query generation
- job evaluation

### Current State

The current cover letter flow lives in:

- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/services/cover_letter.py)
- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\resumes.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/routers/resumes.py)
- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\prompts\templates.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/prompts/templates.py)

`generate_cover_letter(...)` currently:

- formats a plain prompt from the shared prompt template
- resolves output language
- calls `app.llm.complete(...)` directly
- returns stripped plain text

This works, but the AI task boundary is still implicit and inconsistent with the two newer LangChain-backed slices.

### Design Decision

Use the same low-risk migration pattern already used for search queries and job evaluation:

1. Keep `backend/app/services/cover_letter.py` as the product/service layer entrypoint.
2. Move only the LLM-heavy cover letter generation into `backend/app/ai/tasks/generate_cover_letter.py`.
3. Keep LiteLLM as the runtime gateway through the existing AI invocation adapter pattern.
4. Preserve the existing cover letter return type: plain text string.

This is a minimal extraction, not a rewrite of the entire content-generation service.

### What Moves Into The AI Task

Add a dedicated prompt and task layer for cover letters:

- `backend/app/ai/prompts/generate_cover_letter.py`
- `backend/app/ai/tasks/generate_cover_letter.py`

The task will own:

- prompt construction
- LangChain runnable pipeline
- model invocation through the LiteLLM adapter
- plain-text result normalization

Task input will include:

- structured `resume_data`
- `job_description`
- `language`

Task output will be:

- one plain-text cover letter string

### What Stays In The Service Layer

`backend/app/services/cover_letter.py` will continue to own:

- language resolution through existing helpers
- public service entrypoint names
- compatibility for existing routers and background flows

This keeps router and storage behavior unchanged while making the LLM portion reusable and more consistent.

### API And Frontend Compatibility

The following must remain unchanged:

- existing resume improvement flow that optionally generates `cover_letter`
- existing on-demand cover letter generation endpoint
- stored `cover_letter` field shape in resume records
- any frontend rendering or editing of cover letters

No frontend changes are part of this slice.

### Error Handling

This slice should preserve current cover letter failure behavior:

- task-layer invocation errors should still surface back to the existing service/route flow the same way
- text normalization should be conservative: trim whitespace, but do not rewrite content

Unlike search query generation, this slice does not need a heuristic text fallback. It should preserve current error semantics.

### Testing Strategy

Add focused backend coverage only:

1. Unit tests for the new cover letter task runnable path
2. Unit tests confirming `generate_cover_letter(...)` now delegates to the new task
3. Existing resume-related integration or service tests must remain green

The success condition is:

- cover letter generation still returns plain text
- routers and resume workflows do not change behavior
- the LLM portion now lives behind a reusable AI task interface
- backend and career ops CI still pass

### Out Of Scope

This slice will not:

- migrate outreach message yet
- migrate resume title generation yet
- redesign the cover letter prompt content rules
- change stored resume schema
- change any frontend UX
- introduce LangGraph

### File Plan

New files:

- `backend/app/ai/prompts/generate_cover_letter.py`
- `backend/app/ai/tasks/generate_cover_letter.py`
- `backend/tests/unit/test_generate_cover_letter_task.py`

Modified files:

- `backend/app/ai/tasks/__init__.py`
- `backend/app/services/cover_letter.py`

### Recommendation

Proceed with cover letter only in this slice. Do not combine outreach or title generation into the same change. The goal is to keep the migration small, verifiable, and consistent with the two LangChain slices already landed.
