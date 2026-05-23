# Job Ranking And Evidence Tailoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve broad job search recall while improving post-search job ranking and automatically generating a tailored preview when the user selects an actionable job.

**Architecture:** Add deterministic JD understanding and resume evidence matching in the Career Ops evaluator, expose priority metadata on the existing evaluation response, and add a selected-job preview endpoint that evaluates the stored resume/JD before delegating to the existing resume preview flow. Keep search query generation broad and unchanged.

**Tech Stack:** Python, FastAPI, Pydantic, pytest, existing backend service modules.

---

### Task 1: Ranking Metadata

**Files:**
- Modify: `backend/app/schemas/models.py`
- Modify: `backend/app/career_ops/evaluator.py`
- Test: `backend/tests/unit/test_career_ops_evaluator.py`

- [ ] Write failing tests for `priority_label`, `hard_gaps`, and evidence paths.
- [ ] Run the targeted evaluator tests and confirm they fail because fields/functions are missing.
- [ ] Add Pydantic models for evidence matches and priority metadata.
- [ ] Implement deterministic JD requirement extraction and resume evidence matching.
- [ ] Integrate priority metadata into `evaluate_job_fit`.
- [ ] Run targeted evaluator tests and confirm they pass.

### Task 2: Selected Job Auto Preview

**Files:**
- Modify: `backend/app/schemas/models.py`
- Modify: `backend/app/routers/resumes.py`
- Test: `backend/tests/integration/test_resume_api.py`

- [ ] Write failing integration tests for selected high-priority preview and selected skip behavior.
- [ ] Run the targeted resume API tests and confirm they fail because the endpoint is missing.
- [ ] Add request schema with `resume_id`, `job_id`, and `override_skip`.
- [ ] Add endpoint that evaluates the stored resume/JD, blocks skip without override, and otherwise calls the existing preview flow.
- [ ] Run targeted resume API tests and confirm they pass.

### Task 3: Fit Map Prompt Context

**Files:**
- Modify: `backend/app/services/improver.py`
- Modify: `backend/app/prompts/templates.py`
- Test: `backend/tests/service/test_improver.py`

- [ ] Write a failing prompt test proving fit-map context is included in diff generation.
- [ ] Run the targeted improver test and confirm it fails.
- [ ] Add an optional `fit_map` argument to diff generation and include it in the diff prompt.
- [ ] Run targeted improver tests and confirm they pass.

### Task 4: Verification

**Files:**
- Run existing backend tests touched by this feature.

- [ ] Run evaluator, improver, search-query, and resume API tests.
- [ ] Confirm no search-query behavior was narrowed.
- [ ] Review `git diff` to ensure unrelated existing changes were not reverted.
