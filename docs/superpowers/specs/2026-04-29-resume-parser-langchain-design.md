## Resume Parser LangChain Integration Design

Date: 2026-04-29  
Status: Proposed  
Scope: Backend AI task layer only

### Goal

Migrate structured resume parsing into the backend AI task layer without changing current upload behavior, stored resume shape, document parsing flow, or the LiteLLM runtime gateway.

This is the sixth LangChain migration slice after:

- search query generation
- job evaluation
- cover letter generation
- outreach message generation
- resume title generation

### Current State

The current parsing flow lives in:

- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\services\parser.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/services/parser.py)
- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\resumes.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/routers/resumes.py)
- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\prompts\templates.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/prompts/templates.py)

`parse_resume_to_json(...)` currently:

- builds a structured parsing prompt from `PARSE_RESUME_PROMPT`
- calls `app.llm.complete_json(...)` directly
- restores month-inclusive dates from raw markdown
- validates the result against `ResumeData`
- returns a validated dump

This works, but it still bypasses the AI task layer now used by newer LangChain-backed slices.

### Design Decision

Use the same low-risk migration pattern already used for search queries and job evaluation:

1. Keep `backend/app/services/parser.py` as the product/service layer entrypoint.
2. Move only the LLM-heavy structured parsing into `backend/app/ai/tasks/parse_resume.py`.
3. Keep LiteLLM as the runtime gateway through the existing JSON invocation adapter pattern.
4. Preserve the current service-layer post-processing:
   - month/date restoration from raw markdown
   - `ResumeData` validation

This is a minimal extraction, not a rewrite of the whole document parsing pipeline.

### What Moves Into The AI Task

Add a dedicated prompt, parser, and task layer for structured resume parsing:

- `backend/app/ai/prompts/parse_resume.py`
- `backend/app/ai/parsers/parse_resume.py`
- `backend/app/ai/tasks/parse_resume.py`

The task will own:

- prompt construction
- LangChain runnable pipeline
- model invocation through the LiteLLM JSON adapter
- normalization/parsing of the raw JSON result into a typed task result

Task input will include:

- `markdown_text`

Task output will be:

- structured resume data in a validated intermediate task result that maps cleanly to `ResumeData`

### What Stays In The Service Layer

`backend/app/services/parser.py` will continue to own:

- document conversion from binary file to markdown
- month/date restoration from raw markdown
- final `ResumeData` schema validation
- public service entrypoint names used by routers

This keeps the upload and reparse flows unchanged while moving the LLM-heavy extraction behind a reusable AI task boundary.

### API And Frontend Compatibility

The following must remain unchanged:

- file upload flow in the resume router
- stored `processed_data` shape in resume records
- reparsing existing markdown content
- any frontend behavior that depends on the parsed resume shape

No frontend changes are part of this slice.

### Error Handling

This slice should preserve current parser failure behavior:

- task-layer invocation errors should still surface back to the existing service/route flow the same way
- task-layer parsing errors should be explicit and typed
- service-layer date restoration and schema validation should remain the final guardrails

Unlike content-generation slices, this one must keep strong structured-output guarantees.

### Testing Strategy

Add focused backend coverage only:

1. Unit tests for the new resume-parse parser/task runnable path
2. Unit tests confirming `parse_resume_to_json(...)` now delegates to the new task
3. Unit tests confirming date restoration still applies after the task returns
4. Existing resume-related integration or service tests must remain green

The success condition is:

- parsed resumes still validate against `ResumeData`
- month-inclusive dates still get restored from raw markdown
- upload/reparse behavior does not change
- the LLM portion now lives behind a reusable AI task interface
- backend and career ops CI still pass

### Out Of Scope

This slice will not:

- change markitdown document conversion
- redesign the resume parsing prompt schema
- change stored resume schema
- change any frontend UX
- introduce LangGraph

### File Plan

New files:

- `backend/app/ai/prompts/parse_resume.py`
- `backend/app/ai/parsers/parse_resume.py`
- `backend/app/ai/tasks/parse_resume.py`
- `backend/tests/unit/test_parse_resume_task.py`

Modified files:

- `backend/app/ai/tasks/__init__.py`
- `backend/app/services/parser.py`

### Recommendation

Proceed with resume parsing next. Compared with job-score heuristics, this is a much cleaner LLM boundary and will strengthen the AI task layer where structured extraction matters most.
