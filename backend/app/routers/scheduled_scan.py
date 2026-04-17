"""Scheduled scan settings endpoints."""

from fastapi import APIRouter

from app.career_ops.scheduled_scan import (
    build_scheduled_scan_settings_response,
    list_recent_new_jobs,
    list_high_score_unapplied_jobs,
    load_multilingual_resume_assets,
    load_scheduled_scan_config,
    mark_job_status,
    save_scheduled_scan_config,
)
from app.schemas import (
    DiscoveredJobRecord,
    DiscoveredJobStatusUpdateRequest,
    MultilingualResumeAssets,
    ScheduledScanConfig,
    ScheduledScanConfigUpdateRequest,
    ScheduledScanSettingsResponse,
)

router = APIRouter(prefix="/scheduled-scan", tags=["Scheduled Scan"])


@router.get("/settings", response_model=ScheduledScanSettingsResponse)
async def get_scheduled_scan_settings() -> ScheduledScanSettingsResponse:
    config = ScheduledScanConfig.model_validate(load_scheduled_scan_config())
    return ScheduledScanSettingsResponse(
        config=config,
        assets=MultilingualResumeAssets.model_validate(load_multilingual_resume_assets()),
        recent_new_jobs=list_recent_new_jobs(),
        high_score_unapplied_jobs=list_high_score_unapplied_jobs(config.high_score_threshold),
    )


@router.put("/settings", response_model=ScheduledScanSettingsResponse)
async def update_scheduled_scan_settings(
    payload: ScheduledScanConfigUpdateRequest,
) -> ScheduledScanSettingsResponse:
    saved = save_scheduled_scan_config(payload.model_dump(exclude_none=True))
    config = ScheduledScanConfig.model_validate(saved)
    return ScheduledScanSettingsResponse(
        config=config,
        assets=MultilingualResumeAssets.model_validate(load_multilingual_resume_assets()),
        recent_new_jobs=list_recent_new_jobs(),
        high_score_unapplied_jobs=list_high_score_unapplied_jobs(config.high_score_threshold),
    )


@router.post("/jobs/status", response_model=DiscoveredJobRecord)
async def update_discovered_job_status(
    payload: DiscoveredJobStatusUpdateRequest,
) -> DiscoveredJobRecord:
    return DiscoveredJobRecord.model_validate(
        mark_job_status(payload.job_key, payload.status)
    )
