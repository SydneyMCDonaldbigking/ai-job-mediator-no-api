# Multilingual Scheduled Job Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add multilingual resume slots, daily scheduled scan configuration, backend due-run orchestration, persistent new-job history, and a frontend settings/results experience for automatic job discovery.

**Architecture:** Extend the existing backend with three focused services: multilingual resume asset resolution, scheduled scan configuration/state, and a serial scan orchestrator that reuses source-specific search pipelines. Keep the frontend in the current Chainlit app, adding one settings-oriented flow and a recent-results view rather than introducing a separate web frontend.

**Tech Stack:** Python, FastAPI, TinyDB, Playwright, Pydantic, Chainlit, pytest, unittest

---

### Task 1: Add failing backend tests for multilingual resume asset registry and source eligibility

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_scheduled_scan_service.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\scheduled_scan.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_scheduled_scan_service.py`

- [ ] **Step 1: Write the failing test**

```python
from app.career_ops.scheduled_scan import (
    build_multilingual_resume_assets,
    get_enabled_sources,
)


def test_build_multilingual_resume_assets_tracks_language_slots():
    assets = build_multilingual_resume_assets(
        resume_en_id="resume-en",
        resume_ja_id="resume-ja",
        resume_zh_id=None,
    )

    assert assets.resume_en_id == "resume-en"
    assert assets.resume_ja_id == "resume-ja"
    assert assets.resume_zh_id is None


def test_get_enabled_sources_requires_language_resume():
    assets = build_multilingual_resume_assets(
        resume_en_id="resume-en",
        resume_ja_id=None,
        resume_zh_id=None,
    )
    config = {
        "seek_enabled": True,
        "doda_enabled": True,
        "boss_enabled": True,
    }

    sources = get_enabled_sources(assets, config)

    assert sources == ["seek"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py -v`
Expected: FAIL with `ModuleNotFoundError` or missing helper errors for the scheduled scan service.

- [ ] **Step 3: Write minimal implementation**

```python
class MultilingualResumeAssets(BaseModel):
    candidate_id: str = "default"
    resume_en_id: str | None = None
    resume_ja_id: str | None = None
    resume_zh_id: str | None = None


def build_multilingual_resume_assets(
    *,
    resume_en_id: str | None,
    resume_ja_id: str | None,
    resume_zh_id: str | None,
) -> MultilingualResumeAssets:
    return MultilingualResumeAssets(
        resume_en_id=resume_en_id,
        resume_ja_id=resume_ja_id,
        resume_zh_id=resume_zh_id,
    )


def get_enabled_sources(
    assets: MultilingualResumeAssets,
    config: dict[str, Any],
) -> list[str]:
    sources: list[str] = []
    if config.get("seek_enabled") and assets.resume_en_id:
        sources.append("seek")
    if config.get("doda_enabled") and assets.resume_ja_id:
        sources.append("doda")
    if config.get("boss_enabled") and assets.resume_zh_id:
        sources.append("boss")
    return sources
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_scheduled_scan_service.py backend/app/schemas/models.py backend/app/career_ops/scheduled_scan.py
git commit -m "test: add multilingual resume registry coverage"
```

### Task 2: Add failing backend tests for due-time calculation and same-day run suppression

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_scheduled_scan_service.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\scheduled_scan.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_scheduled_scan_service.py`

- [ ] **Step 1: Write the failing test**

```python
from datetime import datetime

from app.career_ops.scheduled_scan import should_run_scheduled_scan


def test_should_run_scheduled_scan_when_time_has_arrived_and_not_run_today():
    due = should_run_scheduled_scan(
        now_local=datetime(2026, 4, 17, 9, 5),
        enabled=True,
        run_time_local="09:00",
        last_run_date_local=None,
    )

    assert due is True


def test_should_not_run_twice_on_same_local_date():
    due = should_run_scheduled_scan(
        now_local=datetime(2026, 4, 17, 9, 5),
        enabled=True,
        run_time_local="09:00",
        last_run_date_local="2026-04-17",
    )

    assert due is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py -v`
Expected: FAIL because `should_run_scheduled_scan` is missing.

- [ ] **Step 3: Write minimal implementation**

```python
def should_run_scheduled_scan(
    *,
    now_local: datetime,
    enabled: bool,
    run_time_local: str,
    last_run_date_local: str | None,
) -> bool:
    if not enabled:
        return False
    hour, minute = [int(part) for part in run_time_local.split(":")]
    if (now_local.hour, now_local.minute) < (hour, minute):
        return False
    if last_run_date_local == now_local.date().isoformat():
        return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_scheduled_scan_service.py backend/app/career_ops/scheduled_scan.py
git commit -m "feat: add scheduled scan due-time rules"
```

### Task 3: Add failing backend service tests for new-job persistence and run-summary updates

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_scheduled_scan_service.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\database.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\career_ops\scheduled_scan.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_scheduled_scan_service.py`

- [ ] **Step 1: Write the failing test**

```python
from app.career_ops.scheduled_scan import persist_discovered_jobs
from app.schemas.models import SeekSearchJob


def test_persist_discovered_jobs_marks_first_seen_job_as_new(tmp_path):
    jobs = [
        SeekSearchJob(
            job_id="seek:https://www.seek.com.au/job/123",
            search_keyword="python backend engineer",
            title="Senior Backend Engineer",
            company="Example Co",
            location="Sydney NSW",
            job_url="https://www.seek.com.au/job/123",
            match_score=0.9,
        )
    ]

    result = persist_discovered_jobs(jobs, existing_jobs={})

    assert result.new_jobs[0].is_new is True
    assert result.stats["new_jobs"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py -v`
Expected: FAIL because the persistence helper and discovered-job models are missing.

- [ ] **Step 3: Write minimal implementation**

```python
class DiscoveredJobRecord(BaseModel):
    job_key: str
    source: str
    resume_language: str
    title: str
    company: str
    location: str = ""
    job_url: str = ""
    summary: str | None = None
    match_score: float = 0.0
    discovered_at: str
    first_seen_at: str
    last_seen_at: str
    is_new: bool = True


def persist_discovered_jobs(
    jobs: list[SeekSearchJob],
    *,
    existing_jobs: dict[str, DiscoveredJobRecord],
) -> PersistenceResult:
    now = datetime.now(timezone.utc).isoformat()
    new_jobs: list[DiscoveredJobRecord] = []
    for job in jobs:
        key = job.job_id
        if key in existing_jobs:
            existing_jobs[key].last_seen_at = now
            existing_jobs[key].is_new = False
            continue
        new_jobs.append(
            DiscoveredJobRecord(
                job_key=key,
                source=job.source,
                resume_language="en",
                title=job.title,
                company=job.company,
                location=job.location,
                job_url=job.job_url,
                summary=job.summary,
                match_score=job.match_score,
                discovered_at=now,
                first_seen_at=now,
                last_seen_at=now,
                is_new=True,
            )
        )
    return PersistenceResult(new_jobs=new_jobs, stats={"new_jobs": len(new_jobs)})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_scheduled_scan_service.py backend/app/database.py backend/app/career_ops/scheduled_scan.py backend/app/schemas/models.py
git commit -m "feat: add discovered job persistence for scheduled scans"
```

### Task 4: Add failing backend API tests for scheduled scan settings and recent results

**Files:**
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_scheduled_scan_api.py`
- Create: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\routers\scheduled_scan.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\main.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\__init__.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\app\schemas\models.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_scheduled_scan_api.py`

- [ ] **Step 1: Write the failing test**

```python
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient

from app.main import app


@patch("app.routers.scheduled_scan.load_scheduled_scan_config")
async def test_get_scheduled_scan_settings(mock_load):
    mock_load.return_value = {
        "enabled": True,
        "run_time_local": "09:00",
        "timezone": "Australia/Sydney",
        "seek_enabled": True,
        "doda_enabled": False,
        "boss_enabled": False,
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/scheduled-scan/settings")

    assert response.status_code == 200
    assert response.json()["run_time_local"] == "09:00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest backend/tests/integration/test_scheduled_scan_api.py -v`
Expected: FAIL with missing router or 404 errors.

- [ ] **Step 3: Write minimal implementation**

```python
router = APIRouter(prefix="/scheduled-scan", tags=["Scheduled Scan"])


@router.get("/settings", response_model=ScheduledScanConfig)
async def get_scheduled_scan_settings() -> ScheduledScanConfig:
    return ScheduledScanConfig.model_validate(load_scheduled_scan_config())


@router.put("/settings", response_model=ScheduledScanConfig)
async def update_scheduled_scan_settings(
    payload: ScheduledScanConfigUpdateRequest,
) -> ScheduledScanConfig:
    saved = save_scheduled_scan_config(payload.model_dump(exclude_none=True))
    return ScheduledScanConfig.model_validate(saved)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest backend/tests/integration/test_scheduled_scan_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/integration/test_scheduled_scan_api.py backend/app/routers/scheduled_scan.py backend/app/main.py backend/app/schemas/models.py backend/app/schemas/__init__.py
git commit -m "feat: add scheduled scan settings api"
```

### Task 5: Add failing frontend tests for scheduled scan settings rendering and source availability

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`

- [ ] **Step 1: Write the failing test**

```python
def test_format_scheduled_scan_settings_shows_disabled_source_without_resume(self):
    frontend_app = load_frontend_app_module()

    message = frontend_app.format_scheduled_scan_settings(
        frontend_app.ScheduledScanSettingsResponse.model_validate(
            {
                "config": {
                    "enabled": True,
                    "run_time_local": "09:00",
                    "timezone": "Australia/Sydney",
                    "seek_enabled": True,
                    "doda_enabled": True,
                    "boss_enabled": False,
                },
                "assets": {
                    "resume_en_id": "resume-en",
                    "resume_ja_id": None,
                    "resume_zh_id": None,
                },
                "recent_new_jobs": [],
            }
        )
    )

    self.assertIn("SEEK", message)
    self.assertIn("未上传日文简历", message)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: FAIL because scheduled scan models and formatter helpers are missing.

- [ ] **Step 3: Write minimal implementation**

```python
class ScheduledScanConfig(BaseModel):
    enabled: bool = False
    run_time_local: str = "09:00"
    timezone: str = "Australia/Sydney"
    seek_enabled: bool = False
    doda_enabled: bool = False
    boss_enabled: bool = False


class ScheduledScanAssets(BaseModel):
    resume_en_id: str | None = None
    resume_ja_id: str | None = None
    resume_zh_id: str | None = None


class ScheduledScanSettingsResponse(BaseModel):
    config: ScheduledScanConfig
    assets: ScheduledScanAssets
    recent_new_jobs: list[dict[str, Any]] = Field(default_factory=list)


def format_scheduled_scan_settings(result: ScheduledScanSettingsResponse) -> str:
    lines = [
        "### 自动扫描设置",
        f"- 启用：`{result.config.enabled}`",
        f"- 每日时间：`{result.config.run_time_local}`",
    ]
    if not result.assets.resume_ja_id:
        lines.append("- doda：未上传日文简历")
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/test_career_ops_frontend.py frontend/app.py
git commit -m "feat: add scheduled scan settings frontend models"
```

### Task 6: Implement frontend actions for settings management and recent results

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\app.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_real_backend_smoke.py`
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\smoke_backend_server.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_real_backend_smoke.py`

- [ ] **Step 1: Write the failing test**

```python
async def test_get_scheduled_scan_settings_uses_backend_route(self):
    RecordingAsyncClient.responses = {
        (
            "GET",
            "http://backend/api/v1/scheduled-scan/settings",
        ): MockHTTPResponse(
            {
                "config": {
                    "enabled": True,
                    "run_time_local": "09:00",
                    "timezone": "Australia/Sydney",
                    "seek_enabled": True,
                    "doda_enabled": False,
                    "boss_enabled": False,
                },
                "assets": {
                    "resume_en_id": "resume-en",
                    "resume_ja_id": None,
                    "resume_zh_id": None,
                },
                "recent_new_jobs": [],
            }
        )
    }

    backend = self.frontend_app.ResumeMatcherBackend("http://backend")
    with patch.object(self.frontend_app.httpx, "AsyncClient", RecordingAsyncClient):
        await backend.get_scheduled_scan_settings()

    self.assertEqual(
        RecordingAsyncClient.requests[0][:2],
        ("GET", "http://backend/api/v1/scheduled-scan/settings"),
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: FAIL because the client methods and action handlers do not exist.

- [ ] **Step 3: Write minimal implementation**

```python
ACTION_VIEW_SCHEDULED_SCAN = "career_ops_view_scheduled_scan"


async def get_scheduled_scan_settings(self) -> ScheduledScanSettingsResponse:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{self.base_url}/api/v1/scheduled-scan/settings")
    response.raise_for_status()
    return ScheduledScanSettingsResponse.model_validate(response.json())


async def handle_view_scheduled_scan_request() -> None:
    result = await backend.get_scheduled_scan_settings()
    await cl.Message(
        content=format_scheduled_scan_settings(result),
        actions=build_tool_actions(),
    ).send()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/app.py frontend/test_career_ops_frontend.py frontend/test_real_backend_smoke.py backend/tests/smoke_backend_server.py
git commit -m "feat: wire scheduled scan settings into frontend"
```

### Task 7: Verify scheduled scan backend, frontend, and smoke behavior

**Files:**
- Modify: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\scripts\run_career_ops_ci.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\unit\test_scheduled_scan_service.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\backend\tests\integration\test_scheduled_scan_api.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_career_ops_frontend.py`
- Test: `C:\Users\zzyyds\Desktop\go_find_a_job\ai-job-mediator\frontend\test_real_backend_smoke.py`

- [ ] **Step 1: Run targeted backend tests**

Run: `python -m pytest backend/tests/unit/test_scheduled_scan_service.py backend/tests/integration/test_scheduled_scan_api.py -v`
Expected: PASS

- [ ] **Step 2: Run targeted frontend tests**

Run: `python -m unittest frontend.test_career_ops_frontend -v`
Expected: PASS

- [ ] **Step 3: Run real-backend smoke tests**

Run: `python -m unittest frontend.test_real_backend_smoke -v`
Expected: PASS with the scheduled scan settings flow visible through the smoke stub.

- [ ] **Step 4: Run aggregate verification**

Run: `python .\scripts\run_career_ops_ci.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/tests/unit/test_scheduled_scan_service.py backend/tests/integration/test_scheduled_scan_api.py frontend/test_career_ops_frontend.py frontend/test_real_backend_smoke.py scripts/run_career_ops_ci.py
git commit -m "test: verify multilingual scheduled scan flow"
```
