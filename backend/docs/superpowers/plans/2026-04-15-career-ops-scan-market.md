# Career Ops Scan + Market Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Python-native portal scanning plus live market-signal enrichment for Career Ops evaluation without disrupting the existing FastAPI backend.

**Architecture:** Introduce a focused `scanner.py` service for Greenhouse/Ashby/Lever discovery with YAML-backed configuration and TSV dedup history, then add a `market_data.py` service that performs live web lookups and feeds Block D of the job evaluator. Expose scanning through one API endpoint and keep portal configuration under the existing config router so frontend wiring can reuse stable JSON contracts later.

**Tech Stack:** FastAPI, Pydantic, TinyDB-adjacent file persistence, PyYAML, httpx, pytest

---

### Task 1: Portal Config + Scanner Service

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\scanner.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\data\portals.example.yml`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\config.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\__init__.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_career_ops_scanner.py`

- [ ] **Step 1: Write the failing scanner tests**

```python
def test_detect_api_handles_greenhouse_ashby_and_lever():
    assert detect_api({"api": "https://boards-api.greenhouse.io/v1/boards/acme/jobs"})["type"] == "greenhouse"
    assert detect_api({"careers_url": "https://jobs.ashbyhq.com/acme"})["type"] == "ashby"
    assert detect_api({"careers_url": "https://jobs.lever.co/acme"})["type"] == "lever"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_career_ops_scanner.py -v`
Expected: FAIL because `app.career_ops.scanner` and scanner schemas do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
def detect_api(company: dict[str, str]) -> dict[str, str] | None:
    if company.get("api", "").find("greenhouse") != -1:
        return {"type": "greenhouse", "url": company["api"]}
    # ashby / lever inference ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_career_ops_scanner.py -v`
Expected: PASS

### Task 2: Scan Endpoint + Portals Config Endpoint

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\career_ops.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\config.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_career_ops_scan_api.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_portals_config_api.py`

- [ ] **Step 1: Write the failing endpoint tests**

```python
async def test_scan_jobs_returns_new_offers():
    response = await client.post("/api/scan-jobs")
    assert response.status_code == 200
    assert response.json()["data"]["new_offers"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_career_ops_scan_api.py tests/integration/test_portals_config_api.py -v`
Expected: FAIL because routes are not registered yet.

- [ ] **Step 3: Write minimal implementation**

```python
@router.post("/scan-jobs")
async def scan_jobs_endpoint() -> CareerOpsScanResponse:
    result = await scan_portals()
    return CareerOpsScanResponse(request_id=str(uuid4()), data=result)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_career_ops_scan_api.py tests/integration/test_portals_config_api.py -v`
Expected: PASS

### Task 3: Live Market Data for Block D

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\market_data.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\evaluator.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\__init__.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_career_ops_market_data.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_career_ops_api.py`

- [ ] **Step 1: Write the failing market-data tests**

```python
async def test_fetch_market_signals_extracts_salary_snippets():
    result = await fetch_market_signals("Senior Backend Engineer", company_name="OpenAI")
    assert result.sources
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_career_ops_market_data.py tests/integration/test_career_ops_api.py -v`
Expected: FAIL because `market_data.py` and the new response fields do not exist yet.

- [ ] **Step 3: Write minimal implementation**

```python
async def fetch_market_signals(role_query: str, company_name: str | None = None) -> MarketSignalData:
    html = await fetch_search_html(role_query)
    return parse_market_snippets(html)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_career_ops_market_data.py tests/integration/test_career_ops_api.py -v`
Expected: PASS

### Task 4: Full Verification

**Files:**
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests`

- [ ] **Step 1: Run focused tests**

```bash
pytest tests/unit/test_career_ops_scanner.py \
       tests/unit/test_career_ops_market_data.py \
       tests/integration/test_career_ops_scan_api.py \
       tests/integration/test_portals_config_api.py \
       tests/integration/test_career_ops_api.py -v
```

- [ ] **Step 2: Run the full backend suite**

```bash
pytest -v
```

- [ ] **Step 3: Run one live smoke scan and one live market-data lookup**

```bash
python - <<'PY'
import asyncio
from app.career_ops.scanner import scan_portals
from app.career_ops.market_data import fetch_market_signals

async def main():
    print(await scan_portals(limit_companies=1))
    print(await fetch_market_signals("Senior Backend Engineer", "OpenAI"))

asyncio.run(main())
PY
```

- [ ] **Step 4: Confirm expected results**

Expected:
- scanner returns a structured summary without crashing
- market data includes live sources or an explicit “no live data” note
- full test suite stays green
