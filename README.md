# AI Job Mediator

Research copy of the AI job mediator project for version control and collaboration.

This repository keeps the full application code, including backend, frontend, tests, docs, and scripts. Personal runtime data and private API configuration are intentionally not committed.

## What Is Included

- FastAPI backend under `backend/`
- Chainlit frontend under `frontend/`
- Backend and frontend tests
- Planning/design docs under `docs/`
- Example configuration files such as `backend/.env.example` and `backend/data/portals.example.yml`

## What Is Not Included

The following local/private files are excluded from git:

- `backend/.env`
- `frontend/.env`
- `config.json`
- `backend/data/database.json`
- `backend/data/portals.yml`
- `backend/data/scan-history.tsv`
- `frontend/data/chats/`
- `frontend/data/users.json`
- `frontend/public/chat-assets/`
- Uploaded resumes, generated PDFs, local logs, temp folders, caches, and virtual environments

## Backend Setup

```powershell
cd backend
copy .env.example .env
# Edit .env with your own provider/API settings.
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

Backend URL:

```text
http://localhost:8000
```

## Frontend Setup

Open a second terminal:

```powershell
cd frontend
python -m pip install -r requirements.txt
$env:BACKEND_URL="http://localhost:8000"
python -m chainlit run app.py --port 8001
```

Frontend URL:

```text
http://localhost:8001
```

Default local login:

```text
username: local-user
password: job-mediator-123
```

You can override those with:

- `CHAINLIT_APP_USERNAME`
- `CHAINLIT_APP_PASSWORD`
- `CHAINLIT_APP_DISPLAY_NAME`
- `CHAINLIT_AUTH_SECRET`

## Tests

Backend:

```powershell
cd backend
python -m pytest
```

Frontend:

```powershell
cd frontend
python -m unittest
```

## Notes For Collaborators

Create your own `.env` and local data files from the examples. Do not commit personal resumes, generated chat assets, API keys, webhook URLs, or local databases.
