from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.career_ops.doda_search import run_manual_doda_search
from app.career_ops.seek_search import run_manual_seek_search
from app.database import db
from app.schemas.models import (
    DiscoveredJobRecord,
    MultilingualResumeAssets,
    ScheduledScanConfig,
    ScheduledScanSettingsResponse,
    SeekSearchJob,
)
from app.services.feishu import send_feishu_webhook_message

logger = logging.getLogger(__name__)

_scheduler_task: asyncio.Task | None = None
_scheduler_stop: asyncio.Event | None = None


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


def load_multilingual_resume_assets() -> dict[str, Any]:
    return MultilingualResumeAssets.model_validate(
        db.get_multilingual_resume_assets() or {}
    ).model_dump()


def load_scheduled_scan_config() -> dict[str, Any]:
    return ScheduledScanConfig.model_validate(
        db.get_scheduled_scan_config() or {}
    ).model_dump()


def save_scheduled_scan_config(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = ScheduledScanConfig.model_validate(payload)
    return db.save_scheduled_scan_config(normalized.model_dump())


def list_recent_new_jobs(limit: int = 10) -> list[dict[str, Any]]:
    jobs = [DiscoveredJobRecord.model_validate(item) for item in db.list_recent_discovered_jobs(limit=limit)]
    return [job.model_dump() for job in jobs]


def list_high_score_unapplied_jobs(
    threshold: float,
    limit: int = 10,
) -> list[dict[str, Any]]:
    jobs = [
        DiscoveredJobRecord.model_validate(item)
        for item in db.list_recent_discovered_jobs(limit=200)
    ]
    filtered = filter_high_score_unapplied_jobs(jobs, threshold=threshold)
    return [job.model_dump() for job in filtered[:limit]]


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


def _job_key(job: SeekSearchJob) -> str:
    if job.job_url:
        return f"{job.source}:{job.job_url}"
    return f"{job.source}:{job.title}|{job.company}|{job.location}"


@dataclass
class PersistenceResult:
    new_jobs: list[DiscoveredJobRecord]
    stats: dict[str, int]


def persist_discovered_jobs(
    jobs: list[SeekSearchJob],
    *,
    existing_jobs: dict[str, Any],
    resume_language: str = "en",
) -> PersistenceResult:
    now = datetime.now(timezone.utc).isoformat()
    new_jobs: list[DiscoveredJobRecord] = []
    to_upsert: list[dict[str, Any]] = []
    seen_count = 0

    for job in jobs:
        key = _job_key(job)
        existing = existing_jobs.get(key)
        if existing:
            record = DiscoveredJobRecord.model_validate(existing)
            record.last_seen_at = now
            record.is_new = False
            seen_count += 1
            to_upsert.append(record.model_dump())
            continue

        record = DiscoveredJobRecord(
            job_key=key,
            source=job.source,
            resume_language=resume_language,
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
            status="new",
        )
        new_jobs.append(record)
        to_upsert.append(record.model_dump())

    if to_upsert:
        db.upsert_discovered_jobs(to_upsert)

    return PersistenceResult(
        new_jobs=new_jobs,
        stats={"new_jobs": len(new_jobs), "existing_jobs": seen_count},
    )


def build_scheduled_scan_settings_response() -> ScheduledScanSettingsResponse:
    config = ScheduledScanConfig.model_validate(load_scheduled_scan_config())
    return ScheduledScanSettingsResponse(
        config=config,
        assets=MultilingualResumeAssets.model_validate(load_multilingual_resume_assets()),
        recent_new_jobs=[
            DiscoveredJobRecord.model_validate(item)
            for item in list_recent_new_jobs()
        ],
        high_score_unapplied_jobs=[
            DiscoveredJobRecord.model_validate(item)
            for item in list_high_score_unapplied_jobs(config.high_score_threshold)
        ],
    )


def filter_high_score_unapplied_jobs(
    jobs: list[DiscoveredJobRecord],
    *,
    threshold: float,
) -> list[DiscoveredJobRecord]:
    filtered = [
        job
        for job in jobs
        if job.match_score >= threshold and job.status != "applied"
    ]
    filtered.sort(key=lambda item: item.match_score, reverse=True)
    return filtered


def mark_job_status(job_key: str, status: str) -> DiscoveredJobRecord:
    existing_jobs = db.get_discovered_jobs_map()
    existing = existing_jobs.get(job_key)
    if not existing:
        raise ValueError(f"Discovered job not found: {job_key}")

    record = DiscoveredJobRecord.model_validate(existing)
    record.status = status
    db.upsert_discovered_jobs([record.model_dump()])
    return record


def build_feishu_notification_lines(new_jobs: list[DiscoveredJobRecord]) -> list[str]:
    lines = [
        "AI Job Mediator 自动扫描发现了新的岗位：",
        "",
    ]
    for index, job in enumerate(new_jobs[:10], start=1):
        location = f" | {job.location}" if job.location else ""
        score = f"{job.match_score:.2f}"
        lines.append(
            f"{index}. [{job.source.upper()}] {job.title} | {job.company}{location} | score {score}"
        )
        if job.job_url:
            lines.append(job.job_url)
    return lines


async def run_due_scheduled_scan_once() -> None:
    config = ScheduledScanConfig.model_validate(load_scheduled_scan_config())
    assets = MultilingualResumeAssets.model_validate(load_multilingual_resume_assets())
    zone = ZoneInfo(config.timezone)
    now_local = datetime.now(zone)

    if not should_run_scheduled_scan(
        now_local=now_local,
        enabled=config.enabled,
        run_time_local=config.run_time_local,
        last_run_date_local=config.last_run_date_local,
    ):
        return

    enabled_sources = get_enabled_sources(assets, config.model_dump())
    result_counts: dict[str, Any] = {}
    errors: list[str] = []
    all_new_jobs: list[DiscoveredJobRecord] = []

    if "seek" in enabled_sources and assets.resume_en_id:
        try:
            result = await run_manual_seek_search(resume_id=assets.resume_en_id)
            persistence = persist_discovered_jobs(
                result.jobs,
                existing_jobs=db.get_discovered_jobs_map(),
                resume_language="en",
            )
            all_new_jobs.extend(persistence.new_jobs)
            result_counts["seek"] = {
                "raw_jobs_found": result.stats.raw_jobs_found,
                "new_jobs": persistence.stats["new_jobs"],
            }
        except Exception as exc:
            logger.warning("Scheduled SEEK scan failed: %s", exc)
            errors.append(f"seek: {exc}")

    if "doda" in enabled_sources and assets.resume_ja_id:
        try:
            result = await run_manual_doda_search(resume_id=assets.resume_ja_id)
            persistence = persist_discovered_jobs(
                result.jobs,
                existing_jobs=db.get_discovered_jobs_map(),
                resume_language="ja",
            )
            all_new_jobs.extend(persistence.new_jobs)
            result_counts["doda"] = {
                "raw_jobs_found": result.stats.raw_jobs_found,
                "new_jobs": persistence.stats["new_jobs"],
            }
        except Exception as exc:
            logger.warning("Scheduled doda scan failed: %s", exc)
            errors.append(f"doda: {exc}")

    high_score_unapplied_jobs = filter_high_score_unapplied_jobs(
        all_new_jobs,
        threshold=config.high_score_threshold,
    )

    if high_score_unapplied_jobs and config.feishu_enabled and config.feishu_webhook_url:
        try:
            await send_feishu_webhook_message(
                config.feishu_webhook_url,
                build_feishu_notification_lines(high_score_unapplied_jobs),
            )
        except Exception as exc:
            logger.warning("Feishu notification failed: %s", exc)
            errors.append(f"feishu: {exc}")

    status = "success" if not errors else ("partial_success" if result_counts else "failed")
    save_scheduled_scan_config(
        {
            "last_run_at": datetime.now(timezone.utc).isoformat(),
            "last_run_date_local": now_local.date().isoformat(),
            "last_run_status": status,
            "last_error": "; ".join(errors) if errors else None,
            "last_result_counts": result_counts,
        }
    )


async def _scheduled_scan_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            await run_due_scheduled_scan_once()
        except Exception as exc:  # pragma: no cover - defensive path
            logger.warning("Scheduled scan loop iteration failed: %s", exc)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            continue


async def start_scheduled_scan_loop() -> None:
    global _scheduler_task, _scheduler_stop
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_stop = asyncio.Event()
    _scheduler_task = asyncio.create_task(_scheduled_scan_loop(_scheduler_stop))


async def stop_scheduled_scan_loop() -> None:
    global _scheduler_task, _scheduler_stop
    if _scheduler_stop is not None:
        _scheduler_stop.set()
    if _scheduler_task is not None:
        await _scheduler_task
    _scheduler_task = None
    _scheduler_stop = None
