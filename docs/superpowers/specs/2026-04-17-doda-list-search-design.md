# doda List Search Design

## Goal

Add a first-pass doda job discovery workflow that uses the candidate's Japanese resume to generate Japanese search keywords, searches doda list pages, extracts only first-page job cards, and feeds the results into the existing unified job-search, scheduled-scan, ranking, and notification pipeline.

## Scope

This design intentionally covers only the first doda delivery slice:

- one source: `doda`
- one scraping depth: list cards only
- one page depth per query: first result page only
- one keyword source: Japanese resume only
- one location model: reuse the shared `country + location_text` configuration and localize it for doda
- two trigger modes:
  - manual search
  - scheduled scan

This design does not include:

- detail-page scraping
- pagination
- login-required flows
- `BOSS直聘`
- a standalone doda UI
- a separate doda-only notification system

## Product Rules

The existing multilingual resume model remains the source-selection boundary:

- English resume powers `SEEK`
- Japanese resume powers `doda`
- Chinese resume powers `BOSS直聘`

The system should not translate English SEEK keywords into Japanese for doda.  
Instead, doda search terms should be generated directly from the current Japanese resume asset.

The location model should remain shared across sources:

- `country`
- `location_text`

Before searching doda, the app should convert the shared location into a doda-friendly Japanese location string.  
The first version should prefer a small deterministic mapping table for common locations and fall back to the original configured text when no mapping exists.

## User Experience

The user should not see a new doda-specific page.

The feature should behave like an extension of the existing job discovery workflow:

1. If a Japanese resume exists, doda becomes an eligible source.
2. Manual search can include doda results.
3. Scheduled scan can include doda when enabled.
4. New and high-score unapplied jobs can include doda entries.
5. The frontend should show the source label so users can distinguish `SEEK` from `doda`.

The product should continue to feel like one unified job-search assistant rather than separate source-specific tools.

## Architecture

The implementation should mirror the existing SEEK boundary so doda becomes just another source adapter.

### 1. doda Search Plan Builder

Responsibility:

- read the active Japanese resume
- derive a lightweight Japanese candidate profile summary
- generate a batch of Japanese doda-oriented keywords
- convert shared location settings into a doda-friendly Japanese location string

This unit decides what to search, not how to scrape.

### 2. doda Scraper

Responsibility:

- build a doda search URL from `keyword + localized_location`
- load the first result page with Playwright
- wait for the list page to stabilize
- capture the first-page HTML

This unit knows about browser automation and doda page structure.

### 3. doda List Parser

Responsibility:

- extract job-card data from doda search result HTML
- return raw doda job records

This unit should not know about scoring, dedupe, scheduled scans, or notifications.

### 4. doda Normalizer

Responsibility:

- map doda raw records into the existing shared job model
- preserve raw location/salary text when normalization is incomplete
- stamp `source = "doda"` and `language = "ja"`

This unit should be small and deterministic.

### 5. Existing Unified Job Pipeline

Responsibility:

- dedupe normalized jobs
- compute match score
- sort and filter results
- persist scheduled-scan discoveries
- feed notifications

This unit already exists and should be reused unchanged whenever possible.

## Data Flow

### Manual Search Flow

1. Frontend triggers manual search.
2. Backend checks which language resumes exist.
3. If Japanese resume is present and doda is enabled for the request, backend builds a doda search plan.
4. Backend runs one doda list-page search per keyword.
5. Backend parses and normalizes doda results.
6. Existing job pipeline dedupes, scores, sorts, and returns results.

### Scheduled Scan Flow

1. Scheduler determines doda is eligible:
   - Japanese resume exists
   - `doda_enabled = true`
2. Scheduled scan orchestrator runs the doda search plan.
3. doda results are normalized into the shared discovered-job model.
4. Existing persistence and notification logic treats them like any other source-specific result.

## Shared Data Model Compatibility

The goal is for doda jobs to use the same shared model as SEEK jobs.

### Required Fields

The first version should reliably populate:

- `source`
- `search_keyword`
- `title`
- `company`
- `job_url`
- `location`
- `salary`

### Optional Fields

The first version should try to populate when available:

- `summary`
- `is_new`

### Nullable Fields

The first version may leave these empty when the list page does not expose them cleanly:

- `work_type`
- `listed_at`

### Recommended Raw-Preservation Fields

To avoid losing useful source data during early normalization, the pipeline should preserve:

- `raw_location_text`
- `raw_salary_text`

## doda List-Page Extraction Rules

The scraper should only depend on stable public list-page information.

Based on current public doda job cards, the first version should expect list pages to expose combinations of:

- title
- company name
- job URL
- location text
- salary text
- "NEW" / new-posting marker
- a mixed snippet that may include workplace details, remote hints, salary context, and other summary text

The first version should not block on perfectly separating every subfield from long mixed snippets.  
It is acceptable to keep summary text coarse as long as the core fields remain correct.

## Search and URL Strategy

The first version should prefer the simplest public path:

- use doda's public search entry
- build a list-search URL from `keyword + location`
- open only the first page
- do not paginate
- do not click into detail pages

If doda exposes multiple possible list formats, choose the one with the most stable public card structure, even if it is not the richest.

## Dedupe Rules

doda should plug into the existing dedupe logic with minimal change.

Primary dedupe key:

- `source + canonical_job_url`

Fallback dedupe key:

- `source + title + company + location`

This means:

- doda jobs dedupe cleanly within doda
- doda and SEEK do not collide with each other

## Scoring Rules

doda match scoring should reuse the existing lightweight ranking model, but only with Japanese inputs:

- Japanese resume profile summary
- Japanese keyword set
- doda title
- doda company
- doda summary text

The system should not mix English SEEK keywords into doda ranking.

The first version should keep scoring lightweight and deterministic, not LLM-heavy.

## Frontend Integration

The frontend should not branch into a separate doda UX.

Instead:

- manual search results should include doda jobs in the same result block
- scheduled-scan result views should include doda jobs in the same lists
- each rendered job should clearly display its `source`

No source-specific frontend flow is required for the first version.

## Notification Compatibility

The existing notification path should remain source-agnostic.

For doda jobs:

- notifications should include the `source`
- only high-score unapplied jobs should notify
- no doda-specific delivery format is needed

## Testing Strategy

The first version should add three testing layers.

### 1. Unit Tests

- Japanese keyword generation from Japanese resume input
- location localization for doda
- raw doda card normalization into shared job model
- dedupe behavior using `source + job_url`

### 2. Parser Fixture Tests

- parse saved doda list-page HTML fixtures
- verify required fields are extracted
- verify missing optional fields do not break normalization

### 3. Integration / Workflow Tests

- manual search includes doda when Japanese resume exists
- scheduled scan includes doda when enabled
- doda jobs appear in recent new jobs / high-score unapplied jobs

The first version should avoid relying on live doda network calls in CI.  
CI should prefer saved fixture HTML for parser verification and mocked integration edges where possible.

## Recommended Delivery Order

1. Add doda search-plan builder using Japanese resume input.
2. Add doda URL builder and list-page scraper.
3. Add doda list parser and normalizer.
4. Reuse existing unified job pipeline for dedupe and scoring.
5. Wire doda into manual search orchestration.
6. Wire doda into scheduled scan orchestration.
7. Add parser fixtures and integration tests.

## Success Criteria

The first doda slice is successful when:

- a Japanese resume enables doda as a valid source
- manual search can return doda jobs
- scheduled scan can discover doda jobs
- doda jobs flow into `recent_new_jobs`
- doda jobs flow into `high_score_unapplied_jobs`
- source labels let the user distinguish doda from SEEK
- the implementation reuses the existing pipeline instead of creating a parallel doda-only subsystem
