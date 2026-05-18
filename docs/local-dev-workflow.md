# Local Dev Workflow

This is the practical local workflow for this repository.

## 1. Install Dependencies

Backend:

```powershell
python -m pip install -e .\backend
```

Frontend:

```powershell
python -m pip install -r .\frontend\requirements.txt
```

Playwright browser:

```powershell
python -m playwright install chromium
```

## 2. Check Local Environment

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\check-local-env.ps1
```

Mac/Linux:

```bash
bash ./scripts/check-local-env.sh
```

The check script reports:

- Python availability
- required Python modules
- Playwright Chromium availability
- resolved backend port
- resolved backend URL

## 3. Start the Backend

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-backend.ps1
```

Mac/Linux:

```bash
bash ./scripts/start-backend.sh
```

Dynamic port priority:

1. `BACKEND_PORT`
2. `PORT`
3. default `8001`

## 4. Start the Frontend

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\start-frontend.ps1
```

Mac/Linux:

```bash
bash ./scripts/start-frontend.sh
```

Frontend backend resolution priority:

1. `BACKEND_URL`
2. `BACKEND_PORT`
3. `PORT`
4. default `http://127.0.0.1:8001`

## 5. Verify Health

Open or request:

```text
http://127.0.0.1:8001/api/v1/health
```

Default frontend URL:

```text
http://127.0.0.1:3000
```

## 6. Run Focused Verification

Dynamic-port regression:

```powershell
python -m pytest backend\tests\unit\test_runtime_port_config.py -v
python -m unittest frontend.test_backend_url_config -v
```

Real frontend/backend smoke:

```powershell
python -m unittest frontend.test_real_backend_smoke -v
```

Broader CI-style check:

```powershell
python .\scripts\run_career_ops_ci.py
```

## Common Problems

### Port 8000 issues on Windows

Do not force `8000`.

Use:

```text
BACKEND_PORT=8001
BACKEND_URL=http://127.0.0.1:8001
```

### Missing Playwright browser

Symptom:

- browser smoke or PDF rendering says executable is missing

Fix:

```powershell
python -m playwright install chromium
```

### Frontend cannot reach backend

Check:

- backend is running
- `BACKEND_URL` matches the backend port
- `FRONTEND_BASE_URL` matches where the frontend is reachable

### Multi-provider LLM confusion

Remember:

- `.env` is for local process-level wiring
- `backend/data/config.json` is for runtime provider keys and `llm_fallback_chain`
