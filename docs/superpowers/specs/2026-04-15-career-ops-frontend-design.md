# Career Ops Frontend Design

## Goal

Wire the new Career Ops backend capabilities into the existing Chainlit frontend without replacing the current chat-first UX.

## Context

The frontend is a single `app.py` Chainlit application that already handles:

- resume upload and restore
- JD analysis via preview tailoring
- resume optimization via existing backend routes

The new backend capabilities to expose are:

- `POST /api/evaluate-job`
- `POST /api/scan-jobs`
- `GET/PUT /api/v1/config/portals`

## Interaction Model

Use a hybrid interaction model:

- explicit Chainlit action buttons for discoverability
- keyword-based text routing as a fallback
- short follow-up prompts when an action needs user input, such as a JD or edited portals config

This keeps the current structure intact and avoids introducing a separate frontend framework.

## UX Flow

### A-F Job Evaluation

- Add an action button that asks the user to paste a JD.
- When a JD arrives, call `POST /api/evaluate-job` with the current resume content.
- Render:
  - overall score and label
  - A-F block scores
  - executive summary
  - tailoring priorities
  - interview focus
  - market data, including salary mentions and source links

### Job Scanning

- Add an action button and text trigger for scanning.
- Call `POST /api/scan-jobs`.
- Render a compact summary:
  - companies scanned
  - total jobs found
  - duplicates filtered
  - new offers with title, company, location, source, and link
  - any scan errors

### Portals Configuration

- Add actions for viewing and editing portals config.
- View uses `GET /api/v1/config/portals` and shows YAML in a fenced block.
- Edit sets a pending state and asks the user to paste YAML or JSON.
- On submission, parse the content client-side and send structured JSON to `PUT /api/v1/config/portals`.
- Show the saved summary after update.

## State Handling

Add lightweight session keys in `app.py`:

- pending frontend action
- optional draft portals mode flag

No persistent database changes are needed on the frontend side.

## Error Handling

- Reuse the existing `httpx` error handling style.
- Add friendly validation messages for malformed YAML or JSON.
- If a requested action requires a resume and none is uploaded, guide the user back to upload first.

## Testing

Add focused frontend unit tests for:

- keyword routing helpers
- result formatting helpers
- portals config parsing and rendering
- backend client methods for new endpoints with mocked HTTP transport
