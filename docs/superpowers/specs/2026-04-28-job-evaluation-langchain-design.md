## Job Evaluation LangChain Integration Design

Date: 2026-04-28  
Status: Proposed  
Scope: Backend AI task layer only

### Goal

Migrate the LLM-heavy portion of job evaluation into the new `backend/app/ai/` task layer without changing frontend behavior, API shape, PDF generation inputs, or the existing LiteLLM runtime gateway.

This is the second LangChain migration slice after search query generation.

### Current State

The current evaluation flow lives in:

- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\evaluator.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/career_ops/evaluator.py)
- [C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\career_ops.py](/C:/Users/zzyyds/Desktop/go_find_a_job/ai-job-mediator/backend/app/routers/career_ops.py)

`evaluate_job_fit(...)` currently mixes several responsibilities:

- resume normalization and text formatting
- job description preparation
- market signal enrichment
- prompt construction
- LLM invocation
- structured evaluation parsing
- A-F score aggregation
- response schema shaping

That makes it functional, but the AI task boundary is less explicit than it should be.

### Design Decision

Use the same migration pattern as the completed search query slice:

1. Keep `backend/app/career_ops/evaluator.py` as the product service layer.
2. Move only the LLM task portion into `backend/app/ai/tasks/evaluate_job.py`.
3. Keep LiteLLM as the model gateway through the LangChain runnable adapter.
4. Preserve the existing response shape returned by `evaluate_job_fit(...)`.

This is a minimal extraction, not a full evaluator rewrite.

### What Moves Into The AI Task

Add a new AI task with prompt, parser, and runnable support:

- `backend/app/ai/prompts/evaluate_job.py`
- `backend/app/ai/parsers/evaluate_job.py`
- `backend/app/ai/tasks/evaluate_job.py`

The task will own:

- evaluation prompt template
- structured JSON output contract
- LangChain runnable pipeline
- conversion from raw model JSON into typed evaluation task data

The task input will include:

- formatted resume text
- job description text
- extracted keyword targets
- market signal summary if available

The task output will be a structured list of evaluation dimensions plus supporting rationale fields in the shape already expected by the evaluator service.

### What Stays In The Product Service

`backend/app/career_ops/evaluator.py` will continue to own:

- resume coercion and normalization
- resume-to-text formatting
- keyword extraction
- market signal fetch and fallback behavior
- final A-F score summarization
- assembling `CareerOpsEvaluationData`

This preserves the current non-LLM business logic and keeps the task boundary clean.

### API And Frontend Compatibility

The following must remain unchanged:

- `POST /api/evaluate-job`
- frontend evaluation request shape
- frontend response rendering
- PDF generation code paths that depend on evaluation data

No frontend or router contract changes are part of this slice.

### Error Handling

The task layer should follow the same rule as search query generation:

- runtime invocation failures may fall back only if there is an existing evaluator-safe fallback path
- schema or parser failures after a successful model response should surface as errors, not silently degrade

For this slice, the evaluator service should keep its current exception behavior at the API boundary.

### Testing Strategy

Add focused backend coverage only:

1. Unit tests for the new evaluation parser
2. Unit tests for the new evaluation task runnable path
3. Unit tests confirming `evaluate_job_fit(...)` now delegates to the new task while preserving output shape
4. Existing evaluation integration tests or adjacent Career Ops tests must remain green

The success condition is:

- current evaluation behavior is preserved
- the LLM portion now lives behind a reusable AI task interface
- full backend and career ops CI still pass

### Out Of Scope

This slice will not:

- redesign the A-F scoring rubric
- change PDF layout or tailoring behavior
- migrate resume parsing
- migrate cover letter or outreach generation
- introduce LangGraph
- change frontend interaction patterns

### File Plan

New files:

- `backend/app/ai/prompts/evaluate_job.py`
- `backend/app/ai/parsers/evaluate_job.py`
- `backend/app/ai/tasks/evaluate_job.py`
- `backend/tests/unit/test_evaluate_job_task.py`

Modified files:

- `backend/app/career_ops/evaluator.py`
- any minimal AI package exports needed under `backend/app/ai/tasks/__init__.py`
- existing evaluation unit tests if present and still relevant

### Recommendation

Proceed with the minimal task extraction only. Do not broaden this into a full evaluator refactor during the same change. The goal is to make `job evaluation` LangChain-ready with the same low-risk pattern that already worked for `generate_search_queries`.
