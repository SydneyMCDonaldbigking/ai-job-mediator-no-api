# SEEK Manual Job Search Design

## Goal

Add a first-pass SEEK job discovery workflow that lets the existing app generate a batch of search keywords from the candidate's resume, search SEEK manually on demand, scrape only the search result list, and return normalized ranked jobs to the current chat-first UX.

## Scope

This design intentionally covers only the first implementation slice:

- one source: SEEK
- one trigger mode: manual user action
- one page depth per query: first result page only
- one scraping depth: list cards only, no detail pages
- one result lifecycle: in-memory aggregation for the current request

This design does not include:

- scheduled scans
- push notifications such as Feishu or WhatsApp
- cross-run job history persistence
- application autofill or auto-apply flows
- support for doda, BOSS 直聘, or any non-SEEK source

## Context

The project already has:

- resume upload and parsing flows
- resume analysis and optimization workflows
- a chat-first Chainlit frontend
- backend support for structured resume data
- Playwright already present in the stack for PDF rendering

That means a SEEK scraper can fit naturally into the backend without introducing a brand new runtime dependency model. The right boundary is to keep browser scraping isolated behind a source-specific scraper module so the rest of the product remains unaware of Playwright details.

## User Experience

The user flow for this first version is:

1. The candidate uploads or restores a resume.
2. The candidate triggers a new frontend action such as `SEEK 搜索岗位`.
3. The backend derives a candidate search profile from the current resume.
4. The backend generates a batch of SEEK search keywords plus a target location.
5. The backend runs one SEEK list-page search per keyword.
6. The backend merges, deduplicates, scores, and sorts the jobs.
7. The frontend renders the resulting jobs plus summary stats and per-keyword errors.

The frontend should keep the experience simple:

- one explicit action button to trigger the workflow
- one compact status/update message while the backend runs
- one final result block with summary stats and ranked jobs

No new standalone page or separate frontend app is needed.

## Architecture

The implementation should be split into four clear units.

### 1. Resume Profile Service

Responsibility:

- read the current candidate resume content or structured resume data
- derive a lightweight candidate profile summary
- generate a batch of SEEK-oriented search keywords
- produce a location string for SEEK searches

This unit decides what to search for, not how to scrape.

### 2. SEEK Scraper

Responsibility:

- build a SEEK search URL from `keyword + location`
- load the list page with Playwright
- wait for the result list to stabilize
- extract job card fields from the first page only

This unit knows about SEEK DOM structure and Playwright, but nothing about resume scoring rules.

### 3. Job Pipeline

Responsibility:

- normalize raw scraped cards into one internal job model
- deduplicate jobs across keyword searches
- compute a lightweight match score
- sort jobs for display
- assemble stats and non-fatal errors

This unit knows about ranking and aggregation, but not about browser automation internals.

### 4. Manual Search Entry Point

Responsibility:

- expose one backend route that orchestrates the full flow
- connect the route to one frontend action in the current Chainlit app
- return results in a UI-friendly payload

This unit is orchestration only and should not contain scraping logic.

## Data Flow

The request pipeline should be:

1. Frontend sends a manual search request.
2. Backend resolves the active resume context.
3. Resume Profile Service returns a `SearchPlan`.
4. Backend iterates through the generated keyword list.
5. SEEK Scraper runs once per keyword.
6. Job Pipeline combines all raw jobs into normalized jobs.
7. Backend returns:
   - the search plan
   - ranked jobs
   - summary stats
   - per-query errors

This structure is intentionally compatible with later extensions such as scheduled scans and outbound notifications. Those later features should call the same orchestration logic instead of reimplementing search behavior.

## Data Model

The first version should define two core response objects plus lightweight metadata.

### SearchPlan

Fields:

- `resume_id`
- `source` with fixed value `seek`
- `candidate_profile_summary`
- `keywords: list[str]`
- `location: str`

### NormalizedJob

Fields:

- `job_id`
- `source`
- `search_keyword`
- `title`
- `company`
- `location`
- `salary`
- `work_type`
- `listed_at`
- `job_url`
- `summary`
- `match_score`

### SearchStats

Fields:

- `keywords_generated`
- `queries_attempted`
- `queries_succeeded`
- `raw_jobs_found`
- `jobs_after_dedupe`

### SearchError

Fields:

- `search_keyword`
- `message`

## Backend Interface

Add one manual route for the first version:

- `POST /api/v1/jobs/search/seek`

Behavior:

- load the current resume context
- generate search keywords and location
- run the SEEK batch search
- return one combined payload

Suggested response shape:

```json
{
  "plan": {
    "resume_id": "123",
    "source": "seek",
    "candidate_profile_summary": "Senior backend engineer with Python and platform experience",
    "keywords": ["python backend engineer", "platform engineer"],
    "location": "Sydney NSW"
  },
  "jobs": [
    {
      "job_id": "seek:https://www.seek.com.au/job/123",
      "source": "seek",
      "search_keyword": "python backend engineer",
      "title": "Senior Backend Engineer",
      "company": "Example Co",
      "location": "Sydney NSW",
      "salary": "$180k-$200k",
      "work_type": "Full time",
      "listed_at": "2d ago",
      "job_url": "https://www.seek.com.au/job/123",
      "summary": "Build APIs and platform services",
      "match_score": 0.87
    }
  ],
  "stats": {
    "keywords_generated": 2,
    "queries_attempted": 2,
    "queries_succeeded": 2,
    "raw_jobs_found": 34,
    "jobs_after_dedupe": 22
  },
  "errors": []
}
```

## Search Keyword Generation

The Resume Profile Service should produce a batch of SEEK-friendly search terms derived from the candidate resume rather than asking the user to type queries manually.

The first version should optimize for usefulness over sophistication:

- generate a small batch of role-oriented keywords
- bias toward title and skill combinations that match the resume
- reuse existing resume parsing outputs when possible
- avoid overly broad generic terms that flood results

The first version should not require a separate configuration surface for keyword editing.

Keyword generation success criteria:

- a backend/platform-oriented resume should yield queries that resemble actual SEEK titles
- the keyword set should be compact enough to keep the manual run responsive
- repeated runs on the same resume should be stable enough for predictable testing

## SEEK Scraping Strategy

The SEEK scraper should use Playwright because the site is public and searchable without login, while the project already has browser support in its stack.

The first version should follow these rules:

- build the SEEK URL from `keyword + location`
- load the list page only
- wait for visible job results
- scrape only the first page
- do not click into job details
- do not attempt account login
- do not attempt advanced filters beyond keyword and location

Core extracted card fields:

- title
- company
- location
- salary if present
- work type if present
- listed-at text if present
- card summary if present
- destination URL

If SEEK changes structure or some optional fields are missing, the scraper should still return partial jobs instead of failing the whole query.

## Deduplication

The first version should deduplicate only within the current request batch.

Deduplication priority:

1. canonical job URL
2. fallback composite key: `title + company + location`

Only one copy of the same job should remain in the merged result set, even if multiple search keywords return it.

Cross-run historical deduplication is explicitly out of scope for this version.

## Scoring and Ranking

The first version should use lightweight deterministic scoring, not a second LLM pass.

Signals can include:

- title alignment with the candidate profile
- skill keyword matches in title or summary
- location alignment
- seniority alignment
- obvious mismatch penalties for unrelated roles

The score is for sorting and later notification thresholds, not for perfect job-fit judgments. The backend should expose one numeric `match_score` and sort descending before returning jobs.

## Error Handling

Failures should degrade gracefully:

- one failing keyword query must not fail the whole batch
- the response should include successful jobs plus per-keyword errors
- timeouts and missing-list situations should produce diagnostics
- optional fields may be empty without invalidating the job

This matters because later scheduled scans and notifications will need the same error contract.

## Testing Strategy

Testing should be split into three layers.

### Unit Tests

Cover:

- search keyword generation
- SEEK URL construction
- deduplication rules
- match-score calculation

### Parser and Scraper Tests

Cover:

- extraction from saved SEEK list-page HTML fixtures
- normalization when optional fields are missing
- stable parsing without live network dependence

CI should prefer fixture-driven tests rather than live SEEK calls.

### Manual Smoke Test

Cover:

- upload or restore a resume
- trigger the new SEEK search action
- verify generated keywords and location
- verify ranked SEEK jobs render in the frontend
- verify partial success behavior when one query fails

## Implementation Order

Recommended order:

1. Define response models for plan, job, stats, and errors.
2. Build resume-profile keyword generation.
3. Add SEEK URL construction.
4. Implement first-page list scraping with Playwright.
5. Implement normalization, dedupe, and scoring.
6. Expose the backend route.
7. Add the manual frontend action and rendering.
8. Run unit, fixture, and manual smoke tests.

## Risks and Constraints

Known constraints for this version:

- SEEK page structure may change over time
- list-only data may omit detail-page information
- first-page-only search means some relevant jobs will be missed
- keyword generation quality directly affects search usefulness

These tradeoffs are acceptable because this version is intended to validate the end-to-end product loop before adding scheduling, notifications, and other job sources.
