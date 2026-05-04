## Resume Title LangChain Integration Design

Date: 2026-04-29  
Status: Proposed  
Scope: Backend AI task layer only

### Goal

Migrate resume title generation into the backend AI task layer without changing current API behavior, stored resume shape, or the LiteLLM runtime gateway.

This is the fifth LangChain migration slice after:

- search query generation
- job evaluation
- cover letter generation
- outreach message generation

### Current State

The current resume title flow lives in:

- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/services/cover_letter.py)
- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\prompts\templates.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/prompts/templates.py)

`generate_resume_title(...)` currently:

- formats a plain prompt from the shared title template
- resolves output language
- calls `app.llm.complete(...)` directly
- trims quotes and whitespace
- truncates the result to 80 characters

This works, but it still bypasses the AI task layer now used by the newer LangChain-backed slices.

### Design Decision

Use the same low-risk migration pattern already used for cover letter and outreach:

1. Keep `backend/app/services/cover_letter.py` as the product/service layer entrypoint.
2. Move only the LLM-heavy title generation into `backend/app/ai/tasks/generate_resume_title.py`.
3. Keep LiteLLM as the runtime gateway through the existing AI invocation adapter pattern.
4. Preserve the existing resume-title return type: one plain-text string.
5. Preserve the current service-layer post-processing: strip quotes/whitespace and truncate to 80 characters.

This is a minimal extraction, not a rewrite of the full content-generation service.

### What Moves Into The AI Task

Add a dedicated prompt and task layer for resume titles:

- `backend/app/ai/prompts/generate_resume_title.py`
- `backend/app/ai/tasks/generate_resume_title.py`

The task will own:

- prompt construction
- LangChain runnable pipeline
- model invocation through the LiteLLM adapter
- conservative text normalization via `strip()`

Task input will include:

- `job_description`
- `language`

Task output will be:

- one plain-text title string

### What Stays In The Service Layer

`backend/app/services/cover_letter.py` will continue to own:

- public service entrypoint names
- compatibility for existing callers
- current title-specific post-processing:
  - strip surrounding quotes
  - truncate to 80 characters

This keeps existing caller behavior unchanged while moving the LLM portion behind a reusable AI task boundary.

### API And Frontend Compatibility

The following must remain unchanged:

- any route or workflow that consumes generated resume titles
- stored title field shape in resume records
- any frontend display of generated titles

No frontend changes are part of this slice.

### Error Handling

This slice should preserve current resume-title failure behavior:

- task-layer invocation errors should still surface back to the existing service/route flow the same way
- text normalization in the task should stay conservative
- service-layer quote stripping and 80-character cap should remain exactly where they are today

No heuristic fallback is needed for this slice. The goal is behavioral parity with cleaner task boundaries.

### Testing Strategy

Add focused backend coverage only:

1. Unit tests for the new title runnable path
2. Unit tests confirming `generate_resume_title(...)` now delegates to the new task
3. Unit tests confirming the existing title post-processing is preserved
4. Existing resume-related integration or service tests must remain green

The success condition is:

- title generation still returns the same kind of short plain-text string
- current trimming/truncation behavior remains intact
- the LLM portion now lives behind a reusable AI task interface
- backend and career ops CI still pass

### Out Of Scope

This slice will not:

- redesign the title prompt content rules
- change stored resume schema
- change any frontend UX
- introduce LangGraph
- refactor cover-letter or outreach callers again

### File Plan

New files:

- `backend/app/ai/prompts/generate_resume_title.py`
- `backend/app/ai/tasks/generate_resume_title.py`
- `backend/tests/unit/test_generate_resume_title_task.py`

Modified files:

- `backend/app/ai/tasks/__init__.py`
- `backend/app/services/cover_letter.py`

### Recommendation

Proceed with resume title only in this slice. Keep the service-layer cleanup semantics unchanged so the migration stays small, verifiable, and consistent with the LangChain slices already landed.
