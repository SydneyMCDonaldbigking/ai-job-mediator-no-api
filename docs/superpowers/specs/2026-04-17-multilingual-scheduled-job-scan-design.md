# Multilingual Scheduled Job Scan Design

## Goal

Add a scheduled job-discovery workflow that runs once per day at a user-configured local time, chooses job sources based on which language-specific resume files the user has uploaded, reuses the existing search pipeline for each eligible source, and stores newly discovered jobs for later notification and application workflows.

## Scope

This design covers the next delivery slice after manual SEEK search:

- one daily scheduled run at a configured local time
- one global scan configuration bound to the current active candidate profile
- separate uploaded resume assets for English, Japanese, and Chinese
- source enablement driven by available language-specific resumes
- persistent storage for discovered jobs and scan run state
- frontend settings and recent-results UI for the scheduled scan feature

This design does not include:

- outbound notifications such as Feishu or WhatsApp
- automatic form filling or auto-apply
- arbitrary cron expressions
- catch-up backfills for missed runs while the server is offline
- parallel multi-browser scanning in the first version

## Product Rules

The user may upload up to three language-specific resumes as separate files:

- English resume
- Japanese resume
- Chinese resume

Source enablement rules:

- English resume present enables English-market sources such as SEEK
- Japanese resume present enables Japanese-market sources such as doda
- Chinese resume present enables Chinese-market sources such as BOSS 直聘

The system should not auto-translate one resume into another language. Language variants are user-supplied assets.

The scheduled scan configuration is global for the active candidate and always uses the latest uploaded resume for each language slot. Uploading a new file for one language replaces the currently active file for that language.

## User Experience

The frontend should introduce a simple scheduled-scan settings surface with two responsibilities:

1. manage daily scan timing
2. show which language resumes exist and which sources can run

The first version should show:

- whether scheduled scans are enabled
- the daily local execution time in `HH:MM`
- the timezone used for scheduling
- available sources by language
- whether the required language-specific resume is present
- the last scan status and last run time
- the most recent newly discovered jobs

The source toggles should be constrained:

- a source can only be enabled if its required language resume exists
- if the required resume does not exist, the source is disabled in the UI and explained

The user experience should feel like a single “automatic scanning” feature, not three independent bots.

## Architecture

The implementation should be split into five clear units.

### 1. Multilingual Resume Asset Registry

Responsibility:

- track the current active resume file for each language
- expose whether English, Japanese, and Chinese resume variants exist
- resolve the active resume to use for a given source

This unit should not contain scheduler logic.

### 2. Scheduled Scan Configuration Store

Responsibility:

- store whether scheduled scans are enabled
- store the user-configured local run time
- store the timezone
- store per-source enabled flags
- store last run state

This unit should not contain scraping logic.

### 3. Scheduler Loop

Responsibility:

- wake up on a fixed polling interval
- check whether a daily run is due
- prevent duplicate runs on the same local day
- trigger the scan pipeline once per due day

This unit should only orchestrate timing and should not know DOM selectors or rendering details.

### 4. Source Scan Orchestrator

Responsibility:

- determine which sources are eligible based on language resume availability and source toggles
- run the correct search pipeline for each enabled source
- aggregate per-source results and failures
- persist newly discovered jobs and run metadata

This unit sits above individual source adapters.

### 5. Recent Results View Model

Responsibility:

- return last run summary
- return recent newly discovered jobs
- shape the frontend response for the settings/results screen

This unit should not contain scheduler timing rules.

## Scheduling Rules

The first version should support one daily local execution time formatted as `HH:MM`.

Behavior:

- the backend starts a background polling loop when the application boots
- the polling loop checks due state once every 60 seconds
- if scheduled scans are disabled, it exits early for that cycle
- if the current local time is before the configured time, it exits early
- if a scan already ran successfully on the current local date, it exits early
- otherwise it triggers a scheduled scan run

The first version should not attempt same-day catch-up for downtime. If the server is not running at the configured time, that day is skipped and the next day proceeds as normal.

## Source Selection Rules

The source-to-language mapping for the first version is:

- SEEK requires English resume
- doda requires Japanese resume
- BOSS 直聘 requires Chinese resume

For a source to run, both conditions must be true:

1. the source is enabled in scheduled scan settings
2. the required language-specific resume exists

Execution order in the first version should be serial:

1. SEEK
2. doda
3. BOSS 直聘

Serial execution is preferred initially for simpler logging, browser lifecycle handling, and debugging.

## Resume Asset Model

The active multilingual resume registry should represent the current candidate’s language-specific assets.

Suggested fields:

- `candidate_id`
- `resume_en_id`
- `resume_ja_id`
- `resume_zh_id`
- `updated_at`

These fields do not need to preserve old language versions in the first version. Each language slot points to the currently active uploaded file for that language.

## Scheduled Scan Config Model

Suggested fields:

- `enabled`
- `run_time_local`
- `timezone`
- `seek_enabled`
- `doda_enabled`
- `boss_enabled`
- `last_run_at`
- `last_run_date_local`
- `last_run_status`
- `last_error`
- `last_result_counts`

Recommended semantics:

- `run_time_local` uses `HH:MM`
- `timezone` stores an IANA timezone identifier
- `last_run_date_local` prevents duplicate same-day runs
- `last_result_counts` stores a compact per-source result summary

## Discovered Job Model

Scheduled scans should persist discovered jobs separately from chat data and JD uploads.

Suggested fields:

- `job_key`
- `source`
- `resume_language`
- `title`
- `company`
- `location`
- `job_url`
- `summary`
- `match_score`
- `discovered_at`
- `first_seen_at`
- `last_seen_at`
- `is_new`

Rules:

- if the job has never been seen before, persist it and mark it new
- if the job already exists, update `last_seen_at`
- do not delete jobs simply because one scan no longer sees them

## New-Job Detection

The first version should use deterministic keys:

1. primary key: `source + canonical_job_url`
2. fallback key: `source + title + company + location`

This key is used both for deduping within a run and for cross-run “new job” detection.

## Scan Execution Flow

The daily scheduled scan flow should be:

1. scheduler determines a run is due
2. scheduled scan config is loaded
3. multilingual resume assets are loaded
4. eligible sources are derived
5. each source runs in serial using its current active language resume
6. found jobs are normalized
7. persisted history is checked for prior sightings
8. newly discovered jobs are marked and stored
9. run summary and errors are stored
10. recent results endpoint becomes available for frontend display

## Frontend Settings Page

The first version should add a dedicated scheduled-scan settings page or settings section that includes:

- enabled toggle
- daily time input
- timezone field or selector
- source enable toggles
- language resume availability state
- last run summary
- recent new jobs list

Source controls should explain the dependency clearly:

- SEEK requires English resume
- doda requires Japanese resume
- BOSS 直聘 requires Chinese resume

If the required resume is missing, the source toggle should be visually disabled with explanatory text instead of allowing a broken configuration.

## Backend Interfaces

The first version should add backend interfaces for:

- reading and writing scheduled scan config
- reading multilingual resume asset availability
- triggering a scheduled scan run internally
- reading recent scan results and recent new jobs

The daily scheduler should call the same orchestration logic the product can later reuse for manual admin/testing endpoints and notification workflows.

## Error Handling

The system should degrade gracefully:

- one failing source must not fail the whole scheduled run
- per-source failures should be recorded in run metadata
- a missing required resume should skip the source rather than crashing the run
- browser or network errors should be surfaced in the run summary

The last run summary must make it obvious whether the scheduler:

- did not run yet
- ran successfully
- partially succeeded
- failed entirely

## Testing Strategy

Testing should be split into four layers.

### Unit Tests

Cover:

- due-time calculation
- same-day dedupe of scheduled runs
- source eligibility based on language resume availability
- new-job key generation

### Service Tests

Cover:

- orchestrator behavior with mocked source scanners
- persistence of new jobs versus already seen jobs
- last run summary updates

### Frontend Tests

Cover:

- settings payload rendering
- source toggle disabling when a required language resume is missing
- recent result summary rendering

### Smoke Tests

Cover:

- enabling a daily scheduled time
- mocked due execution path
- recent results visible in frontend

## Risks and Constraints

Known first-version constraints:

- no backfill for missed runs while offline
- serial browser execution may be slower as more sources are added
- source-to-language mapping is product-coded rather than fully dynamic
- old resume language versions are replaced, not versioned

These tradeoffs are acceptable because the immediate goal is to make automated discovery reliable before adding notification delivery or auto-application logic.
