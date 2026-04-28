# LangChain Integration Design

Date: 2026-04-27  
Status: Proposed  
Scope: Backend AI orchestration only

## Goal

Introduce LangChain in a way that improves AI task structure without destabilizing the current product.

This project already has working product flows for:

- resume upload and parsing
- job evaluation
- resume tailoring and content generation
- multilingual job search on SEEK and doda
- scheduled scans and notifications

The design goal is not to replace the existing backend architecture. The goal is to add a clean AI task layer that can later grow into richer orchestration, and eventually into LangGraph, while preserving the current LiteLLM-based runtime and existing product services.

## Current State

The backend currently does not use LangChain or LangGraph.

Instead, it relies on:

- `backend/app/llm.py` for provider routing, retries, timeouts, and model invocation
- `litellm` as the model gateway
- service and router code that directly coordinates prompts and model calls
- existing prompt templates under `backend/app/prompts/`

This means the current system already has a working model abstraction layer, but it does not yet have a first-class task orchestration layer.

## Design Principles

This integration should follow five rules:

1. Keep LiteLLM as the model gateway.
2. Add LangChain at the AI task layer, not across the entire backend.
3. Do not migrate every LLM workflow at once.
4. Keep product services, schedulers, scrapers, routers, and persistence outside LangChain.
5. Design new task interfaces so they can later become LangGraph nodes without another large refactor.

## What Should Use LangChain

LangChain should be introduced only for AI tasks whose main job is:

- prompt construction
- model invocation
- structured parsing
- repeatable LLM task composition

The best candidates in this codebase are:

### 1. Search Query Generation

Generate multilingual search keywords from the current resume in order to drive SEEK and doda searches.

This is the best first migration target because:

- inputs are simple
- outputs are structured
- the feature is valuable but not destructive
- it already sits at a clean boundary between resume understanding and job search

### 2. Job Evaluation

The current A-F job evaluation flow is a natural chain task because it transforms job context and resume context into a structured or semi-structured assessment.

### 3. Content Generation

This includes:

- cover letter generation
- outreach generation
- self-introduction style content

These are strong candidates for prompt templates plus structured output or standardized text output handling.

### 4. Resume Parsing

Resume parsing should eventually move into the LangChain task layer, but not in the first migration wave because it is too central to overall system correctness.

### 5. Job Match Scoring

This may later become a hybrid task:

- rule-based baseline scoring
- optional LLM reranking or explanation layer

It should not be the first migration target.

## What Should Not Use LangChain

LangChain should not be introduced into parts of the system whose complexity is primarily non-LLM complexity.

That includes:

### 1. Playwright Scrapers

These include:

- SEEK search scraping
- doda search scraping
- future browser-based site adapters

These are browser automation concerns, not LLM task orchestration concerns.

### 2. Scheduled Scans

The scheduled scan loop is a runtime orchestration and scheduling concern. It may call AI tasks, but it should not itself become a LangChain workflow at this stage.

### 3. Persistence

TinyDB tables, scan history, multilingual resume assets, and applied-job tracking should stay as ordinary storage code.

### 4. FastAPI Routers

Routers should remain thin transport layers that delegate into services.

### 5. Chainlit Frontend Flow

The frontend should not know whether a backend AI task uses direct LiteLLM, LangChain, or a future LangGraph node.

## Target Architecture

The recommended long-term backend shape is:

1. UI and API layer
2. Product service layer
3. AI task layer
4. Model runtime layer

### UI and API Layer

This contains:

- Chainlit frontend integration
- FastAPI routers

Responsibilities:

- collect user input
- return results
- map user actions to service calls

It should not build prompts or manage LangChain internals.

### Product Service Layer

This contains product logic such as:

- resume upload workflows
- job search orchestration
- scheduled scan orchestration
- notification orchestration
- future application automation orchestration

Responsibilities:

- decide which AI task to call
- decide which scraper to call
- decide when to persist data
- combine non-AI runtime logic with AI outputs

This layer stays ordinary Python application code.

### AI Task Layer

This is the main LangChain boundary.

Responsibilities:

- define prompt templates
- define structured output expectations
- invoke models through a consistent interface
- expose stable task entrypoints to services

This layer should become the eventual seam for LangGraph adoption.

### Model Runtime Layer

This remains anchored on existing LiteLLM infrastructure.

Responsibilities:

- provider routing
- retries
- timeouts
- logging
- model selection

The existing `backend/app/llm.py` remains the runtime core for this layer.

## Proposed Directory Structure

The first LangChain integration should introduce a new backend area:

```text
backend/app/ai/
backend/app/ai/core/
backend/app/ai/tasks/
backend/app/ai/prompts/
backend/app/ai/parsers/
```

### `backend/app/ai/core/`

This layer is responsible for adapting the current LiteLLM runtime into something that LangChain tasks can use consistently.

Recommended contents:

- `llm_adapter.py`
- `invoke.py`
- `model_registry.py`

Responsibilities:

- expose a stable AI invocation surface
- preserve current provider routing behavior
- avoid forcing the rest of the codebase to import LiteLLM details directly

### `backend/app/ai/tasks/`

Each file represents one AI product capability.

Recommended first files:

- `generate_search_queries.py`
- `evaluate_job.py`
- `generate_cover_letter.py`
- `generate_outreach.py`
- later `parse_resume.py`
- later `score_jobs.py`

Responsibilities:

- define one clear task per file
- expose task-level entrypoints for service code
- keep prompt assembly and parsing local to the task

### `backend/app/ai/prompts/`

This stores prompt templates used by tasks.

The project already has prompts under `backend/app/prompts/templates.py`.

The migration strategy should be incremental:

- do not move everything immediately
- create new prompt modules for migrated tasks
- allow old and new prompt locations to coexist during transition

### `backend/app/ai/parsers/`

This stores structured output parsing helpers.

Responsibilities:

- convert model output into typed task responses
- isolate parsing logic from service code
- enable consistent fallback and validation behavior

## Runtime Strategy

The current LiteLLM layer should remain in place.

This project should not replace LiteLLM with provider-specific LangChain integrations in the first phase.

Instead, the runtime strategy should be:

- LiteLLM remains the model gateway
- LangChain becomes the task composition layer
- a thin adapter bridges the two

That means the architecture becomes:

`Routers / Chainlit -> Services -> LangChain Tasks -> LiteLLM -> Providers`

This approach preserves current strengths:

- multi-provider flexibility
- existing retry and timeout logic
- existing configuration model
- predictable runtime behavior

## Dependency Strategy

The first migration should keep dependencies minimal.

Recommended initial additions:

- `langchain-core`
- optionally `langchain`

Not recommended in phase one:

- replacing LiteLLM with provider-specific LangChain SDK packages
- adopting a large set of LangChain ecosystem dependencies
- requiring LangGraph immediately

LangGraph may be added later, but it should not be required to gain value from the first migration.

## Migration Order

The migration should proceed in low-risk stages.

### Phase 1: Introduce AI Task Layer

Add the new `backend/app/ai/` structure and create the first task abstraction without changing major product flows.

### Phase 2: Migrate Search Query Generation

Move multilingual search query generation into a dedicated LangChain-backed task.

This is the recommended first migration because it is:

- valuable to current features
- easy to validate
- low-risk compared with parsing or tailoring

### Phase 3: Migrate Job Evaluation

Move A-F evaluation into the new task layer.

### Phase 4: Migrate Content Generation

Migrate:

- cover letters
- outreach
- related generated content

### Phase 5: Consider Resume Parsing Migration

Only after the adapter and task conventions are stable.

### Phase 6: Evaluate LangGraph

Only after several tasks exist with stable interfaces.

LangGraph should be introduced to orchestrate already well-defined tasks, not to compensate for unclear task boundaries.

## First Implementation Scope

The first implementation should stay intentionally small.

It should include:

- adding minimal LangChain dependencies
- creating `backend/app/ai/`
- implementing one runtime adapter layer
- implementing one task:
  - `generate_search_queries`
- wiring existing job-search services to use the new task
- preserving fallback to the current implementation while the migration is being validated

It should not include:

- scraper rewrites
- scheduled scan rewrites
- DB schema changes
- full prompt migration
- LangGraph introduction
- frontend changes driven by LangChain adoption

## Interfaces

The AI task layer should expose task-oriented entrypoints instead of raw prompt helpers.

For example:

- `generate_search_queries(...)`
- `evaluate_job_fit(...)`
- `generate_cover_letter(...)`
- `generate_outreach_message(...)`

Service code should depend on these task interfaces, not on prompt templates or provider invocation helpers.

This keeps LangChain implementation details behind a stable application boundary.

## Error Handling

The new AI task layer must preserve the backend's existing operational discipline.

Requirements:

- provider and timeout behavior should still be controlled by the LiteLLM runtime layer
- parsing failures should be surfaced as task-level errors, not raw model exceptions where possible
- migrated tasks should support fallback to legacy implementations during rollout
- task logs should identify the task name so failures remain diagnosable

## Testing Strategy

The first LangChain migration should extend existing backend test coverage instead of inventing a separate testing model.

Testing should include:

### Unit Tests

- prompt-to-structured-output parsing tests
- adapter tests around invocation behavior
- task-level tests for `generate_search_queries`

### Integration Tests

- API-level tests that confirm search generation still works through the backend route
- migration-path tests proving that current SEEK and doda search flows still receive valid search queries

### Regression Focus

The main regression risk is not routing or scraping.  
The main risk is that query generation behavior changes unexpectedly and harms downstream search quality.

Therefore, tests should explicitly validate:

- multilingual keyword output shape
- stable parsing behavior
- non-empty keyword generation
- compatibility with current job search service contracts

## Success Criteria

The LangChain integration is considered successful when:

- the backend still behaves the same from the frontend's perspective
- search query generation runs through the new AI task layer
- existing SEEK and doda flows continue to work
- the new task structure is easier to extend than the current direct prompt usage
- no large runtime responsibilities are incorrectly moved into LangChain
- the codebase becomes more ready for later LangGraph adoption

## Recommended Next Step

After this design is approved, the next step should be a focused implementation plan for:

- creating the new AI task layer
- adding minimal dependencies
- migrating `generate_search_queries`
- preserving fallback behavior and test coverage
