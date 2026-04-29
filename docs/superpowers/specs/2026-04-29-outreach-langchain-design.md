## Outreach Message LangChain Integration Design

Date: 2026-04-29  
Status: Proposed  
Scope: Backend AI task layer only

### Goal

Migrate outreach message generation into the backend AI task layer without changing current API behavior, resume router flow, storage shape, or the LiteLLM runtime gateway.

This is the fourth LangChain migration slice after:

- search query generation
- job evaluation
- cover letter generation

### Current State

The current outreach message flow lives in:

- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\cover_letter.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/services/cover_letter.py)
- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\resumes.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/routers/resumes.py)
- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\prompts\templates.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/prompts/templates.py)

`generate_outreach_message(...)` currently:

- formats a plain prompt from the shared outreach template
- resolves output language
- calls `app.llm.complete(...)` directly
- returns stripped plain text

This works, but it still bypasses the AI task layer now used by newer LangChain-backed slices.

### Design Decision

Use the same low-risk migration pattern already used for search queries, job evaluation, and cover letters:

1. Keep `backend/app/services/cover_letter.py` as the product/service layer entrypoint.
2. Move only the LLM-heavy outreach generation into `backend/app/ai/tasks/generate_outreach_message.py`.
3. Keep LiteLLM as the runtime gateway through the existing AI invocation adapter pattern.
4. Preserve the existing outreach return type: plain text string.

This is a minimal extraction, not a rewrite of the full content-generation service.

### What Moves Into The AI Task

Add a dedicated prompt and task layer for outreach messages:

- `backend/app/ai/prompts/generate_outreach_message.py`
- `backend/app/ai/tasks/generate_outreach_message.py`

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

- one plain-text outreach message string

### What Stays In The Service Layer

`backend/app/services/cover_letter.py` will continue to own:

- public service entrypoint names
- compatibility for existing routers and background flows
- grouping of content-generation helpers in one service module

This keeps resume router behavior unchanged while moving the LLM-heavy portion behind a reusable AI task boundary.

### API And Frontend Compatibility

The following must remain unchanged:

- existing resume improvement flow that optionally generates `outreach_message`
- any on-demand outreach generation path that already calls the service
- stored `outreach_message` field shape in resume records
- any frontend rendering or editing of outreach content

No frontend changes are part of this slice.

### Error Handling

This slice should preserve current outreach failure behavior:

- task-layer invocation errors should still surface back to the existing service/route flow the same way
- text normalization should stay conservative: trim whitespace, but do not rewrite message content

No heuristic fallback is needed for this slice. The goal is behavioral parity with cleaner task boundaries.

### Testing Strategy

Add focused backend coverage only:

1. Unit tests for the new outreach runnable path
2. Unit tests confirming `generate_outreach_message(...)` now delegates to the new task
3. Existing resume-related integration or service tests must remain green

The success condition is:

- outreach generation still returns plain text
- routers and resume workflows do not change behavior
- the LLM portion now lives behind a reusable AI task interface
- backend and career ops CI still pass

### Out Of Scope

This slice will not:

- migrate resume title generation yet
- redesign outreach prompt content rules
- change stored resume schema
- change any frontend UX
- introduce LangGraph

### File Plan

New files:

- `backend/app/ai/prompts/generate_outreach_message.py`
- `backend/app/ai/tasks/generate_outreach_message.py`
- `backend/tests/unit/test_generate_outreach_message_task.py`

Modified files:

- `backend/app/ai/tasks/__init__.py`
- `backend/app/services/cover_letter.py`

### Recommendation

Proceed with outreach only in this slice. Do not combine resume title generation into the same change. The goal is to keep the migration small, verifiable, and consistent with the LangChain slices already landed.
