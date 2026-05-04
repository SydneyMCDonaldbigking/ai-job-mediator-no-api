# AI Job Mediator No-API Edition

This is a research/shareable copy of the Chainlit frontend. It does not include
the FastAPI backend, LLM provider configuration, API keys, or HTTP backend
client wiring.

## What is included

- Chainlit chat UI
- Local JSON chat history storage
- In-process demo backend for upload, resume analysis, mock search results, and
  PDF download flows
- Existing frontend tests and docs that are useful for studying the UI flow

## What was removed

- `backend/`
- HTTP API data layer
- Backend smoke tests and CI scripts
- Local `.env` files
- HTTP backend-client runtime dependency

## Run locally

```powershell
cd frontend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m chainlit run app.py
```

Then open the Chainlit URL printed in the terminal.

Default local login:

- username: `local-user`
- password: `job-mediator-123`

## Notes

This build is meant for local research and sharing. The job matching, scan, PDF,
and resume actions are backed by in-process mock/demo logic, so it can run
without external services.
