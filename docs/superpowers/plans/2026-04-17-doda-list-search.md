# doda List Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add first-page doda list search using Japanese resumes and route doda results through the existing manual search and scheduled scan pipeline.

**Architecture:** Extend the existing SEEK-oriented job discovery structure with a doda source adapter instead of creating a separate subsystem. Keep doda limited to keyword generation, list-page scraping, normalization, and orchestration wiring so all dedupe, scoring, scheduling, and notification logic stays shared.

**Tech Stack:** FastAPI backend, Pydantic models, Playwright, pytest, Chainlit frontend integration tests

---

## File Map

### Backend search and orchestration

- Modify: `backend/app/career_ops/seek_search.py`
  - Reuse shared search-plan and normalization helpers where possible
  - Add doda-specific plan building, search URL building, parsing, and orchestration glue only if the team keeps this in one file
- Or create: `backend/app/career_ops/doda_search.py`
  - Prefer this if the SEEK file becomes too large; keep doda source logic isolated
- Modify: `backend/app/career_ops/scheduled_scan.py`
  - Add doda to enabled-source selection and scan execution
- Modify: `backend/app/routers/jobs.py`
  - Extend manual job-search route surface for doda, or add a new route if the existing route structure expects one route per source
- Modify: `backend/app/schemas/models.py`
  - Add doda plan/result models only if current shared models need source-specific extensions

### Backend tests

- Create or modify: `backend/tests/unit/test_doda_search_service.py`
- Modify: `backend/tests/unit/test_scheduled_scan_service.py`
- Create or modify: `backend/tests/integration/test_doda_search_api.py`
- Modify: `scripts/run_career_ops_ci.py`

### Frontend

- Modify: `frontend/app.py`
  - Add doda-aware rendering only where the source needs to appear in existing result blocks
- Modify: `frontend/test_career_ops_frontend.py`
- Modify: `frontend/test_real_backend_smoke.py`

---

### Task 1: Add doda Search Service Coverage First

**Files:**
- Create: `backend/tests/unit/test_doda_search_service.py`
- Modify: `backend/app/career_ops/doda_search.py` or `backend/app/career_ops/seek_search.py`

- [ ] **Step 1: Write the failing unit tests for doda keyword generation, location localization, parsing, and normalization**

```python
from backend.app.career_ops.doda_search import (
    build_doda_search_plan,
    build_doda_search_url,
    localize_location_for_doda,
    normalize_doda_job,
    parse_doda_list_html,
)


def test_build_doda_search_plan_generates_japanese_keywords():
    plan = build_doda_search_plan(
        resume_id="resume-ja-1",
        resume_text="PythonとFastAPIを用いたバックエンド開発。AWS経験あり。",
        country="JP",
        location_text="Tokyo",
    )

    assert plan.source == "doda"
    assert plan.location in {"東京", "Tokyo"}
    assert plan.keywords


def test_localize_location_for_doda_maps_common_city():
    assert localize_location_for_doda(country="JP", location_text="Tokyo") == "東京"


def test_parse_doda_list_html_extracts_required_fields():
    html = '''
    <html><body>
      <a href="https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__123/" class="jobLink">
        <div class="title">バックエンドエンジニア</div>
        <div class="company">OpenAI Japan</div>
        <div class="location">東京都</div>
        <div class="salary">年収700万円～1000万円</div>
      </a>
    </body></html>
    '''

    jobs = parse_doda_list_html(html, search_keyword="バックエンドエンジニア")

    assert len(jobs) == 1
    assert jobs[0]["title"] == "バックエンドエンジニア"
    assert jobs[0]["company"] == "OpenAI Japan"
    assert jobs[0]["location"] == "東京都"


def test_normalize_doda_job_sets_source_and_job_id():
    normalized = normalize_doda_job(
        {
            "title": "バックエンドエンジニア",
            "company": "OpenAI Japan",
            "job_url": "https://doda.jp/DodaFront/View/JobSearchDetail/j_jid__123/",
            "location": "東京都",
            "salary": "年収700万円～1000万円",
            "summary": "Python / FastAPI",
            "search_keyword": "バックエンドエンジニア",
        }
    )

    assert normalized.source == "doda"
    assert normalized.job_id.startswith("doda:")
    assert normalized.language == "ja"
```

- [ ] **Step 2: Run the new unit tests to verify they fail**

Run: `python -m pytest backend/tests/unit/test_doda_search_service.py -v`
Expected: FAIL with import or missing implementation errors for the doda helpers

- [ ] **Step 3: Implement the minimal doda search helpers**

```python
def localize_location_for_doda(country: str, location_text: str) -> str:
    mapping = {
        ("JP", "Tokyo"): "東京",
        ("JP", "Osaka"): "大阪",
        ("JP", "Kyoto"): "京都",
    }
    return mapping.get((country.strip().upper(), location_text.strip()), location_text.strip())


def build_doda_search_url(keyword: str, location: str) -> str:
    query = quote_plus(keyword)
    area = quote_plus(location)
    return f"https://doda.jp/DodaFront/View/JobSearchList/j_kw__{query}/-ci__{area}/"


def normalize_doda_job(raw_job: dict[str, Any]) -> NormalizedJob:
    job_url = raw_job["job_url"]
    return NormalizedJob(
        job_id=f"doda:{job_url}",
        source="doda",
        language="ja",
        search_keyword=raw_job["search_keyword"],
        title=raw_job["title"],
        company=raw_job["company"],
        location=raw_job.get("location"),
        salary=raw_job.get("salary"),
        work_type=raw_job.get("work_type"),
        listed_at=raw_job.get("listed_at"),
        job_url=job_url,
        summary=raw_job.get("summary"),
        raw_location_text=raw_job.get("location"),
        raw_salary_text=raw_job.get("salary"),
    )
```

- [ ] **Step 4: Run the doda unit tests again**

Run: `python -m pytest backend/tests/unit/test_doda_search_service.py -v`
Expected: PASS for all newly added doda helper tests

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_doda_search_service.py backend/app/career_ops/doda_search.py
git commit -m "feat: add doda search service helpers"
```

---

### Task 2: Add doda Manual Search API

**Files:**
- Modify: `backend/app/routers/jobs.py`
- Modify: `backend/app/schemas/models.py`
- Create or modify: `backend/tests/integration/test_doda_search_api.py`

- [ ] **Step 1: Write the failing API test for manual doda search**

```python
def test_post_manual_doda_search_returns_jobs(client):
    response = client.post(
        "/api/v1/jobs/search/doda",
        json={"resume_id": "resume-ja-1"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["plan"]["source"] == "doda"
    assert isinstance(payload["jobs"], list)
```

- [ ] **Step 2: Run the doda API test to verify it fails**

Run: `python -m pytest backend/tests/integration/test_doda_search_api.py -v`
Expected: FAIL with 404 or missing route behavior

- [ ] **Step 3: Implement the minimal doda manual search route**

```python
@router.post("/api/v1/jobs/search/doda", response_model=DodaSearchResponse)
async def search_doda_jobs(payload: ManualJobSearchRequest) -> DodaSearchResponse:
    return await run_manual_doda_search(payload.resume_id)
```

- [ ] **Step 4: Run the API test again**

Run: `python -m pytest backend/tests/integration/test_doda_search_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/jobs.py backend/app/schemas/models.py backend/tests/integration/test_doda_search_api.py
git commit -m "feat: add doda manual search api"
```

---

### Task 3: Wire doda into Scheduled Scan

**Files:**
- Modify: `backend/app/career_ops/scheduled_scan.py`
- Modify: `backend/tests/unit/test_scheduled_scan_service.py`

- [ ] **Step 1: Write the failing scheduled-scan tests for doda eligibility and execution**

```python
def test_get_enabled_sources_includes_doda_for_japanese_resume():
    assets = MultilingualResumeAssets(
        candidate_id="default",
        resume_en_id=None,
        resume_ja_id="resume-ja-1",
        resume_zh_id=None,
    )
    config = ScheduledScanConfig(
        enabled=True,
        run_time_local="09:00",
        timezone="Australia/Sydney",
        seek_enabled=False,
        doda_enabled=True,
        boss_enabled=False,
    )

    assert get_enabled_sources(config, assets) == ["doda"]
```

- [ ] **Step 2: Run the scheduled-scan unit tests to verify they fail**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py -v`
Expected: FAIL where doda is not yet included as an enabled source

- [ ] **Step 3: Extend scheduled scan orchestration to run doda**

```python
if "doda" in enabled_sources:
    doda_result = await run_manual_doda_search(assets.resume_ja_id)
    discovered.extend(doda_result.jobs)
    counts["doda"] = len(doda_result.jobs)
```

- [ ] **Step 4: Run scheduled-scan unit tests again**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py -v`
Expected: PASS for doda-related source selection and orchestration cases

- [ ] **Step 5: Commit**

```bash
git add backend/app/career_ops/scheduled_scan.py backend/tests/unit/test_scheduled_scan_service.py
git commit -m "feat: add doda to scheduled scan orchestration"
```

---

### Task 4: Surface doda Results in Frontend Formatting and Smoke Coverage

**Files:**
- Modify: `frontend/app.py`
- Modify: `frontend/test_career_ops_frontend.py`
- Modify: `frontend/test_real_backend_smoke.py`

- [ ] **Step 1: Write the failing frontend formatting test**

```python
def test_format_scan_result_includes_doda_source_label(self):
    result = frontend_app.CareerOpsScanResponse.model_validate(
        {
            "request_id": "scan-1",
            "data": {
                "jobs": [
                    {
                        "source": "doda",
                        "title": "バックエンドエンジニア",
                        "company": "OpenAI Japan",
                        "location": "東京都",
                        "job_url": "https://doda.jp/job/123",
                        "match_score": 0.91,
                    }
                ]
            },
        }
    )

    formatted = frontend_app.format_scan_result(result)
    assert "doda" in formatted
```

- [ ] **Step 2: Run the frontend formatting test to verify it fails**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: FAIL if doda source labels are not preserved in the current formatting path

- [ ] **Step 3: Update frontend formatting and any source-label rendering**

```python
source_label = (job.source or "unknown").upper() if job.source != "doda" else "doda"
```

- [ ] **Step 4: Extend real-backend smoke to accept doda in unified results**

```python
page.get_by_text("doda", exact=False).wait_for(timeout=20000)
```

- [ ] **Step 5: Run frontend and smoke tests**

Run: `python -m unittest frontend.test_career_ops_frontend frontend.test_real_backend_smoke -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add frontend/app.py frontend/test_career_ops_frontend.py frontend/test_real_backend_smoke.py
git commit -m "feat: expose doda results in frontend workflows"
```

---

### Task 5: Add doda Checks to CI and Run End-to-End Verification

**Files:**
- Modify: `scripts/run_career_ops_ci.py`

- [ ] **Step 1: Add doda tests to the CI script**

```python
backend_checks = [
    "backend/tests/integration/test_doda_search_api.py",
    "backend/tests/unit/test_doda_search_service.py",
]
```

- [ ] **Step 2: Run targeted backend tests**

Run: `python -m pytest backend/tests/unit/test_doda_search_service.py backend/tests/integration/test_doda_search_api.py -v`
Expected: PASS

- [ ] **Step 3: Run targeted frontend tests**

Run: `python -m unittest frontend.test_career_ops_frontend frontend.test_real_backend_smoke -v`
Expected: PASS

- [ ] **Step 4: Run the full career ops CI script**

Run: `python .\\scripts\\run_career_ops_ci.py`
Expected: successful completion with doda tests included

- [ ] **Step 5: Commit**

```bash
git add scripts/run_career_ops_ci.py
git commit -m "test: add doda coverage to career ops ci"
```

---

## Self-Review

### Spec coverage

- doda first-page list search: covered in Tasks 1 and 2
- Japanese resume keyword generation: covered in Task 1
- shared location localization for doda: covered in Task 1
- manual search integration: covered in Task 2
- scheduled scan integration: covered in Task 3
- frontend unified source display: covered in Task 4
- CI and verification: covered in Task 5

### Placeholder scan

No `TODO`, `TBD`, `FIXME`, or empty “handle appropriately” tasks remain in this plan.

### Type consistency

The plan consistently assumes:

- `source = "doda"`
- Japanese resume slot is `resume_ja_id`
- shared scheduled scan toggle is `doda_enabled`
- doda list jobs map into the existing shared normalized job model
