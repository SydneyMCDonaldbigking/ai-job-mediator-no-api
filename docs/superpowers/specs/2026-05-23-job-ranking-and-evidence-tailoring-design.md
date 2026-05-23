# Job Ranking And Evidence Tailoring Design

Date: 2026-05-23

## Problem

The current backend can search broadly and can tailor a resume to a JD, but the
quality gap is in the middle:

- Search results are not consistently ranked by whether the role is actually a
  good target for the candidate.
- Evaluation leans too much on keyword overlap and broad A-F scoring, so roles
  that merely look similar can be surfaced too highly.
- Resume tailoring can become shallow keyword weaving because it does not first
  build a requirement-to-evidence map.

The user explicitly wants to keep broad search recall. Narrowing generated search
keywords is out of scope because it risks reducing the job pool.

## Goals

1. Preserve broad job discovery and avoid reducing search result volume.
2. Improve post-search ranking by reading the JD and matching it to resume
   evidence, not just title or keyword overlap.
3. Make each recommendation explain why the job is high priority, worth checking,
   stretch, or skip.
4. Automatically tailor the resume preview when the user selects a job that is
   worth acting on.
5. Make resume tailoring use JD requirements plus resume evidence, so changes are
   precise rather than shallow keyword substitutions.

## Non-Goals

- Do not make search keywords narrower as the primary fix.
- Do not remove existing search paths for SEEK, doda, or configured portals.
- Do not redesign the frontend in this phase.
- Do not invent candidate capabilities, metrics, dates, employers, titles, or
  certifications.

## Proposed Architecture

### 1. Broad Recall Stays Intact

Existing search query generation and portal scanning remain broad. The backend
may keep generic terms like `software engineer`, `backend engineer`, or
`platform engineer` because broad recall is valuable.

The ranking layer becomes responsible for reducing noise after jobs are found.

### 2. JD Understanding Layer

Add a structured JD interpretation step that extracts:

- role lane, such as backend, platform, AI tooling, solutions, data, frontend,
  customer success, sales engineering, or product
- core responsibilities
- hard requirements
- preferred requirements
- seniority signals
- domain or industry signals
- disqualifying or caution signals, such as heavy sales quota, pure frontend,
  security clearance, local-only location, or mandatory technology gaps

This step should be usable by both search-result ranking and resume tailoring.

### 3. Resume Evidence Matching

Add a local evidence map that compares the structured JD requirements against the
resume. Each requirement should receive:

- match status: `strong`, `partial`, `missing`, or `not_applicable`
- evidence paths, such as `summary`, `workExperience[0].description[2]`, or
  `additional.technicalSkills`
- short rationale
- risk note when the match is weak or unsupported

The evidence map is the bridge between "this JD sounds relevant" and "the
candidate can credibly apply."

### 4. Job Priority Gate

Add a final job priority classification:

- `high_priority`: strong lane fit, strong hard-requirement evidence, reasonable
  seniority alignment
- `worth_checking`: good enough to inspect or tailor, with manageable gaps
- `stretch`: plausible but with notable seniority, domain, or requirement gaps
- `skip`: clear mismatch or unsupported hard requirements

The backend should keep skip results available when useful, but mark them clearly
instead of letting them compete with high-quality roles.

### 5. Evidence-Based Resume Tailoring

Before generating resume diffs, build a JD Fit Map from the same JD understanding
and resume evidence layers. The diff prompt should require each proposed change to
reference:

- the JD requirement it supports
- the resume evidence path it is grounded in
- the reason the change improves positioning

Changes for missing requirements must be rejected or avoided unless they can be
framed as adjacent experience without claiming unsupported facts.

## Data Model Additions

Add backend schemas for:

- `JDRequirement`
- `JDUnderstanding`
- `ResumeEvidenceMatch`
- `JobPriorityDecision`
- `JDFitMap`

These can initially live in `backend/app/schemas/models.py` or a focused
career-ops schema module if the model file becomes too crowded.

## API Behavior

`POST /api/v1/evaluate-job` should continue returning the current A-F shape for
compatibility, but enrich the payload with:

- `priority_label`
- `priority_reasons`
- `evidence_matches`
- `hard_gaps`
- `tailoring_ready`

Search endpoints do not need to reduce result count. Later, callers can use the
new fields to sort and group results.

When a user selects a job, the backend should automatically prepare a tailored
resume preview for actionable jobs:

- `high_priority`: auto-generate tailored preview
- `worth_checking`: auto-generate tailored preview
- `stretch`: auto-generate tailored preview only because the user explicitly
  selected it
- `skip`: do not auto-tailor; return the skip reasons and require explicit
  override before tailoring

Resume improvement endpoints should consume the fit map internally when tailoring
against a stored JD. The automatic flow should use preview mode first, not direct
persistence, so the user can inspect changes before saving a tailored resume.

## Testing Strategy

Add tests that prove:

- broad search keyword behavior is not narrowed as part of this change
- a JD with strong title overlap but unsupported hard requirements is classified
  lower than a role with slightly weaker title overlap but stronger evidence
- hard missing requirements appear in `hard_gaps`
- `high_priority` and `worth_checking` decisions include evidence paths
- selecting a high-priority or worth-checking job can trigger tailored preview
  generation without saving it
- selecting a skip job does not auto-tailor unless an explicit override is passed
- resume diff generation includes fit-map context in the prompt
- unsupported JD requirements are not turned into resume changes

## Rollout Plan

1. Add schema and deterministic evidence helpers.
2. Add tests for role priority classification.
3. Integrate the classifier into `evaluate_job_fit`.
4. Add selected-job auto-tailoring preview behavior.
5. Add fit-map context to diff-based resume tailoring.
6. Keep existing API fields working while exposing the new fields for future UI
   grouping and explanations.

## Open Questions

- Should `skip` jobs be hidden by default in the frontend or shown in a collapsed
  section?
- Should the priority gate use only local deterministic logic at first, or allow
  the LLM to propose a classification that local rules then normalize?
