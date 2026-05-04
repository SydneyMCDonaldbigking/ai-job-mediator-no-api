# Frontend Resume State And Response Speed Follow-Ups

> Status: implemented first pass
> Date: 2026-05-04

## Context

After local frontend validation, two follow-up areas need design and implementation.

## 1. Right-Side Tool Panel Resume State

The right-side function panel should read local/backend resume state on startup and reflect whether language-specific resumes already exist.

Required behavior:

- If a resume exists, show a clear status in the corresponding card:
  - Chinese resume exists
  - English resume exists
  - Japanese resume exists
  - Include last upload/update time, for example: `last uploaded: xxx`
- Clicking an existing resume card should still mean re-upload/replace that resume.
- If a resume does not exist, show that no resume is currently available and that upload is required.
- Job search actions should be gated by required language assets:
  - SEEK search requires an English resume.
  - doda search requires a Japanese resume.
- If the required resume is missing, the corresponding search action should be disabled/greyed out and explain what is missing.
- During resume upload/replace, show visible progress instead of leaving the user waiting:
  - show transfer started / uploading
  - show parsing or backend processing in progress
  - show completion or failure
  - keep the progress UI language consistent with the surrounding Chinese frontend

Likely implementation areas:

- Backend resume list/fetch data, if timestamps or language asset metadata need to be exposed.
- `frontend/app.py` action rendering/state payload.
- `frontend/public/auto-login.js` right-side panel rendering and card disabled states.
- Frontend smoke/unit tests around tool panel labels and disabled states.

## 2. Slow Response Time / Parallelism

The app feels too slow during interactive use. Investigate where time is spent and decide whether concurrency can safely improve it.

Questions to answer before changing behavior:

- Which actions are slow: upload parsing, JD evaluation, tailored PDF generation, search, scheduled scan, or all LLM calls?
- Is the bottleneck local LLM/Ollama, remote LLM API latency, PDF rendering, Playwright scraping, Chainlit UI updates, or backend request sequencing?
- Are current LLM calls independent enough to run concurrently?
- If using Ollama, is model serving configured for parallel requests (`num_parallel`) or will parallel calls only queue and become slower?

Potential implementation directions:

- Add timing logs around key backend stages and frontend action handlers.
- Parallelize independent auxiliary generation where safe.
- Use `asyncio.gather(...)` only for truly independent remote calls.
- Move blocking work to worker threads/processes if it blocks the event loop.
- Add UI progress states so slow actions feel less frozen even when total runtime is unchanged.
- Add upload progress feedback for resume transfer and parsing, even if backend processing remains a single request internally.

Guardrails:

- Do not blindly make every LLM call parallel; local Ollama may serialize requests.
- Preserve resume data integrity and current upload/replace semantics.
- Keep disabled states truthful: a greyed action should name the missing prerequisite.

Implemented first pass:

- SEEK manual search now scrapes all generated keywords concurrently.
- doda manual search now scrapes all generated keywords concurrently.
- Scheduled scan now runs enabled SEEK and doda sources concurrently, then persists results sequentially.
- Career Ops portal scanner now fetches enabled company ATS APIs concurrently, then filters/dedupes/writes history sequentially.
- Added tests proving overlap via `max_active == 2` for keyword scraping, enabled source scanning, and company API scanning.
