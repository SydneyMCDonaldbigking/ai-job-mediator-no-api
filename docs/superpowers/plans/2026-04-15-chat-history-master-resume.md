# Chat History And Master Resume Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move chat history metadata into backend TinyDB, add thread deletion and resume re-upload actions, and make new master-resume uploads overwrite the existing master record while exposing ATS PDF download in the frontend.

**Architecture:** Extend backend TinyDB with dedicated chat tables and small `/api/v1/chat` endpoints that mirror the current frontend data-layer contract. Keep frontend asset files local for now, but swap metadata persistence to a backend-backed data layer so upload/session restore, thread history, delete-thread, and PDF generation all run through one backend source of truth.

**Tech Stack:** Python, FastAPI, TinyDB, Chainlit, httpx, unittest, pytest

---

### Task 1: Add failing backend tests for master-resume overwrite and chat history API

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_chat_history_api.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_resume_api.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\resumes.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\__init__.py`

- [ ] **Step 1: Write the failing tests**

```python
async def test_upload_resume_overwrites_existing_master(...):
    ...
    assert data["resume_id"] == "master-123"
```

```python
async def test_chat_thread_round_trip(...):
    ...
    assert payload["data"][0]["id"] == "thread-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests\integration\test_resume_api.py tests\integration\test_chat_history_api.py -v`
Expected: FAIL because overwrite behavior and `/api/v1/chat` routes do not exist yet.

- [ ] **Step 3: Write minimal backend implementation**

```python
master = db.get_master_resume()
if master:
    db.update_resume(master["resume_id"], updates)
else:
    db.create_resume(...)
```

```python
router = APIRouter(prefix="/chat", tags=["Chat History"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests\integration\test_resume_api.py tests\integration\test_chat_history_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/test_resume_api.py backend/tests/integration/test_chat_history_api.py backend/app/routers/resumes.py backend/app/routers/__init__.py
git commit -m "feat: add backend chat history api and master overwrite"
```

### Task 2: Implement backend chat storage and schemas

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\database.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\chat_history.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\chat_history.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\__init__.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\main.py`

- [ ] **Step 1: Write the failing test**

```python
assert response.json()["pageInfo"]["hasNextPage"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests\integration\test_chat_history_api.py -v`
Expected: FAIL because storage methods or response models are incomplete.

- [ ] **Step 3: Write minimal implementation**

```python
@property
def chat_threads(self) -> Table:
    return self.db.table("chat_threads")
```

```python
def upsert_thread(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests\integration\test_chat_history_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py backend/app/chat_history.py backend/app/routers/chat_history.py backend/app/schemas/models.py backend/app/schemas/__init__.py backend/app/main.py
git commit -m "feat: persist chat history in backend tinydb"
```

### Task 3: Add failing frontend tests for remote data layer and ATS PDF client

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_backend_chat_store.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`

- [ ] **Step 1: Write the failing tests**

```python
async def test_generate_tailored_pdf_posts_resume_and_jd(...):
    ...
```

```python
async def test_remote_data_layer_deletes_thread(...):
    ...
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m unittest test_career_ops_frontend test_backend_chat_store -v`
Expected: FAIL because the PDF client and backend-backed data layer do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
async def generate_tailored_pdf(...):
    ...
```

```python
class BackendTinyDBDataLayer(BaseDataLayer):
    ...
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m unittest test_career_ops_frontend test_backend_chat_store -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/test_career_ops_frontend.py frontend/test_backend_chat_store.py frontend/app.py
git commit -m "feat: add frontend pdf client and backend chat store"
```

### Task 4: Wire frontend actions for re-upload, delete thread, PDF download, and migration

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\backend_chat_store.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\local_chat_store.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\requirements.txt`

- [ ] **Step 1: Write the failing test**

```python
assert any(action.label == "下载 ATS PDF" for action in frontend_app.build_tool_actions())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest test_career_ops_frontend test_backend_chat_store -v`
Expected: FAIL because the new actions and migration helper are missing.

- [ ] **Step 3: Write minimal implementation**

```python
cl.Action(name=ACTION_DOWNLOAD_TAILORED_PDF, ...)
```

```python
await data_layer.migrate_local_threads_if_needed(...)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest test_career_ops_frontend test_backend_chat_store -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/backend_chat_store.py frontend/app.py frontend/local_chat_store.py frontend/requirements.txt
git commit -m "feat: wire backend chat storage and ats pdf download"
```

### Task 5: Full verification

**Files:**
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_resume_restore.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_auto_login.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_local_history.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_chat_history_api.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_resume_api.py`

- [ ] **Step 1: Run frontend verification**

Run: `python -m unittest test_career_ops_frontend test_backend_chat_store test_resume_restore test_auto_login test_local_history -v`
Expected: PASS

- [ ] **Step 2: Run backend verification**

Run: `python -m pytest tests\integration\test_resume_api.py tests\integration\test_chat_history_api.py tests\integration\test_career_ops_api.py tests\integration\test_career_ops_scan_api.py tests\integration\test_portals_config_api.py -v`
Expected: PASS

- [ ] **Step 3: Run a lightweight smoke check**

Run: `@'\nimport importlib.util\nfrom pathlib import Path\napp_path = Path(r'C:\\Users\\zzyyds\\Desktop\\go_find_a_job\\ai-job-mediator\\frontend\\app.py')\nspec = importlib.util.spec_from_file_location('frontend_app_module', app_path)\nmodule = importlib.util.module_from_spec(spec)\nassert spec.loader is not None\nspec.loader.exec_module(module)\nprint(len(module.build_tool_actions()))\n'@ | python -`
Expected: Prints action count without import errors.

- [ ] **Step 4: Commit**

```bash
git add frontend backend
git commit -m "feat: unify chat history storage and master resume updates"
```
