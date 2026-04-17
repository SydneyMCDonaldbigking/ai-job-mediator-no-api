# Career Ops Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose Career Ops evaluation, scanner, and portals configuration workflows inside the existing Chainlit frontend.

**Architecture:** Extend the single-file Chainlit app with small helper models, formatter functions, and pending-action state so the new backend routes plug into the current chat workflow cleanly. Keep the existing resume upload and optimization behavior intact while adding explicit tool actions and keyword fallbacks.

**Tech Stack:** Python, Chainlit, httpx, Pydantic, unittest, PyYAML

---

### Task 1: Add failing tests for frontend parsing and formatting helpers

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`

- [ ] **Step 1: Write the failing test**

```python
def test_render_portals_config_as_yaml_contains_company_name():
    frontend_app = load_frontend_app_module()
    rendered = frontend_app.render_portals_config(
        {
            "tracked_companies": [
                {"name": "Anthropic", "careers_url": "https://jobs.example.com"}
            ]
        }
    )
    assert "Anthropic" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: FAIL with `AttributeError` for missing helper functions.

- [ ] **Step 3: Write minimal implementation**

```python
def render_portals_config(config: dict[str, Any]) -> str:
    return yaml.safe_dump(config, sort_keys=False, allow_unicode=True).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/test_career_ops_frontend.py frontend/app.py
git commit -m "test: add frontend helpers coverage for career ops"
```

### Task 2: Add failing tests for new backend client methods

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_scan_jobs_calls_career_ops_endpoint(self):
    backend = frontend_app.ResumeMatcherBackend("http://backend")
    await backend.scan_jobs()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: FAIL because `scan_jobs` does not exist.

- [ ] **Step 3: Write minimal implementation**

```python
async def scan_jobs(self) -> CareerOpsScanResponse:
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(f"{self.base_url}/api/scan-jobs")
    response.raise_for_status()
    return CareerOpsScanResponse.model_validate(response.json())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/test_career_ops_frontend.py frontend/app.py
git commit -m "feat: add career ops client methods to frontend"
```

### Task 3: Wire Chainlit flows for evaluation, scanning, and portals editing

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\requirements.txt`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`

- [ ] **Step 1: Write the failing test**

```python
def test_is_portals_update_request_detects_yaml_block():
    frontend_app = load_frontend_app_module()
    payload = "tracked_companies:\n  - name: Anthropic\n    careers_url: https://jobs.example.com"
    assert frontend_app.parse_portals_config_input(payload)["tracked_companies"][0]["name"] == "Anthropic"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: FAIL because parsing helper is missing.

- [ ] **Step 3: Write minimal implementation**

```python
def parse_portals_config_input(text: str) -> dict[str, Any]:
    loaded = yaml.safe_load(text)
    if not isinstance(loaded, dict):
        raise ValueError("Portals config must be an object")
    return loaded
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app.py frontend/requirements.txt frontend/test_career_ops_frontend.py
git commit -m "feat: wire career ops flows into chainlit frontend"
```

### Task 4: Verify full frontend behavior

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_resume_restore.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_auto_login.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_local_history.py`

- [ ] **Step 1: Run targeted frontend tests**

Run: `python -m unittest frontend.test_career_ops_frontend frontend.test_resume_restore frontend.test_auto_login frontend.test_local_history -v`
Expected: PASS

- [ ] **Step 2: Run backend API tests that cover the connected routes**

Run: `pytest C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_career_ops_scan_api.py C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_portals_config_api.py C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_career_ops_api.py -v`
Expected: PASS

- [ ] **Step 3: Manual smoke check**

Run: `python - <<'PY'\nprint('frontend smoke placeholder')\nPY`
Expected: confirm imports and helper rendering work without syntax errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/app.py frontend/requirements.txt frontend/test_career_ops_frontend.py
git commit -m "test: verify career ops frontend integration"
```
