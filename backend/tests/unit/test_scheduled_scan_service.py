from datetime import datetime
import asyncio
from unittest.mock import AsyncMock, patch

from app.career_ops.scheduled_scan import (
    build_multilingual_resume_assets,
    build_feishu_notification_lines,
    filter_high_score_unapplied_jobs,
    get_enabled_sources,
    mark_job_status,
    persist_discovered_jobs,
    run_due_scheduled_scan_once,
    should_run_scheduled_scan,
)
from app.schemas.models import DiscoveredJobRecord, SeekSearchJob


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


def test_persist_discovered_jobs_marks_first_seen_job_as_new():
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


def test_build_feishu_notification_lines_includes_jobs():
    jobs = [
        DiscoveredJobRecord(
            job_key="seek:https://www.seek.com.au/job/123",
            source="seek",
            resume_language="en",
            title="Senior Backend Engineer",
            company="Example Co",
            location="Sydney NSW",
            job_url="https://www.seek.com.au/job/123",
            summary="Build APIs",
            match_score=0.91,
            discovered_at="2026-04-17T00:05:00+00:00",
            first_seen_at="2026-04-17T00:05:00+00:00",
            last_seen_at="2026-04-17T00:05:00+00:00",
            is_new=True,
        )
    ]

    lines = build_feishu_notification_lines(jobs)

    assert any("SEEK" in line for line in lines)
    assert any("Senior Backend Engineer" in line for line in lines)
    assert any("Example Co" in line for line in lines)


async def test_run_due_scheduled_scan_once_sends_feishu_when_new_jobs_exist():
    seek_response = type(
        "SeekResponse",
        (),
        {
            "jobs": [
                SeekSearchJob(
                    job_id="seek:https://www.seek.com.au/job/123",
                    source="seek",
                    search_keyword="python backend engineer",
                    title="Senior Backend Engineer",
                    company="Example Co",
                    location="Sydney NSW",
                    job_url="https://www.seek.com.au/job/123",
                    match_score=0.91,
                )
            ],
            "stats": type("Stats", (), {"raw_jobs_found": 1})(),
        },
    )()

    with (
        patch(
            "app.career_ops.scheduled_scan.load_scheduled_scan_config",
            return_value={
                "enabled": True,
                "run_time_local": "09:00",
                "timezone": "Australia/Sydney",
                "seek_enabled": True,
                "doda_enabled": False,
                "boss_enabled": False,
                "feishu_enabled": True,
                "feishu_webhook_url": "https://open.feishu.cn/fake-webhook",
                "last_run_date_local": None,
            },
        ),
        patch(
            "app.career_ops.scheduled_scan.load_multilingual_resume_assets",
            return_value={
                "resume_en_id": "resume-en",
                "resume_ja_id": None,
                "resume_zh_id": None,
            },
        ),
        patch(
            "app.career_ops.scheduled_scan.run_manual_seek_search",
            new=AsyncMock(return_value=seek_response),
        ),
        patch(
            "app.career_ops.scheduled_scan.send_feishu_webhook_message",
            new=AsyncMock(),
        ) as mock_feishu,
        patch(
            "app.career_ops.scheduled_scan.should_run_scheduled_scan",
            return_value=True,
        ),
        patch("app.career_ops.scheduled_scan.save_scheduled_scan_config"),
        patch("app.career_ops.scheduled_scan.db.get_discovered_jobs_map", return_value={}),
        patch("app.career_ops.scheduled_scan.db.upsert_discovered_jobs"),
    ):
        await run_due_scheduled_scan_once()

    mock_feishu.assert_awaited_once()


async def test_run_due_scheduled_scan_once_runs_doda_when_japanese_resume_exists():
    doda_response = type(
        "DodaResponse",
        (),
        {
            "jobs": [
                SeekSearchJob(
                    job_id="doda:https://doda.jp/job/123",
                    source="doda",
                    search_keyword="バックエンドエンジニア",
                    title="バックエンドエンジニア",
                    company="OpenAI Japan",
                    location="東京都",
                    job_url="https://doda.jp/job/123",
                    match_score=0.88,
                )
            ],
            "stats": type("Stats", (), {"raw_jobs_found": 1})(),
        },
    )()

    with (
        patch(
            "app.career_ops.scheduled_scan.load_scheduled_scan_config",
            return_value={
                "enabled": True,
                "run_time_local": "09:00",
                "timezone": "Australia/Sydney",
                "seek_enabled": False,
                "doda_enabled": True,
                "boss_enabled": False,
                "feishu_enabled": False,
                "feishu_webhook_url": None,
                "last_run_date_local": None,
            },
        ),
        patch(
            "app.career_ops.scheduled_scan.load_multilingual_resume_assets",
            return_value={
                "resume_en_id": None,
                "resume_ja_id": "resume-ja",
                "resume_zh_id": None,
            },
        ),
        patch(
            "app.career_ops.scheduled_scan.run_manual_doda_search",
            new=AsyncMock(return_value=doda_response),
        ) as mock_doda,
        patch(
            "app.career_ops.scheduled_scan.should_run_scheduled_scan",
            return_value=True,
        ),
        patch("app.career_ops.scheduled_scan.save_scheduled_scan_config"),
        patch("app.career_ops.scheduled_scan.db.get_discovered_jobs_map", return_value={}),
        patch("app.career_ops.scheduled_scan.db.upsert_discovered_jobs"),
    ):
        await run_due_scheduled_scan_once()

    mock_doda.assert_awaited_once()


async def test_run_due_scheduled_scan_once_runs_enabled_sources_concurrently():
    active = 0
    max_active = 0

    def response_for(source: str):
        return type(
            "SearchResponse",
            (),
            {
                "jobs": [
                    SeekSearchJob(
                        job_id=f"{source}:https://example.com/job/123",
                        source=source,
                        search_keyword="backend engineer",
                        title="Backend Engineer",
                        company="Example Co",
                        location="Sydney NSW",
                        job_url=f"https://example.com/{source}/123",
                        match_score=0.91,
                    )
                ],
                "stats": type("Stats", (), {"raw_jobs_found": 1})(),
            },
        )()

    async def fake_search(source: str):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        try:
            await asyncio.sleep(0.05)
        finally:
            active -= 1
        return response_for(source)

    async def fake_seek_search(**_: object):
        return await fake_search("seek")

    async def fake_doda_search(**_: object):
        return await fake_search("doda")

    with (
        patch(
            "app.career_ops.scheduled_scan.load_scheduled_scan_config",
            return_value={
                "enabled": True,
                "run_time_local": "09:00",
                "timezone": "Australia/Sydney",
                "seek_enabled": True,
                "doda_enabled": True,
                "boss_enabled": False,
                "feishu_enabled": False,
                "feishu_webhook_url": None,
                "last_run_date_local": None,
            },
        ),
        patch(
            "app.career_ops.scheduled_scan.load_multilingual_resume_assets",
            return_value={
                "resume_en_id": "resume-en",
                "resume_ja_id": "resume-ja",
                "resume_zh_id": None,
            },
        ),
        patch(
            "app.career_ops.scheduled_scan.run_manual_seek_search",
            new=AsyncMock(side_effect=fake_seek_search),
        ),
        patch(
            "app.career_ops.scheduled_scan.run_manual_doda_search",
            new=AsyncMock(side_effect=fake_doda_search),
        ),
        patch(
            "app.career_ops.scheduled_scan.should_run_scheduled_scan",
            return_value=True,
        ),
        patch("app.career_ops.scheduled_scan.save_scheduled_scan_config"),
        patch("app.career_ops.scheduled_scan.db.get_discovered_jobs_map", return_value={}),
        patch("app.career_ops.scheduled_scan.db.upsert_discovered_jobs"),
    ):
        await run_due_scheduled_scan_once()

    assert max_active == 2


def test_filter_high_score_unapplied_jobs_excludes_applied_and_low_score():
    jobs = [
        DiscoveredJobRecord(
            job_key="seek:https://www.seek.com.au/job/1",
            source="seek",
            resume_language="en",
            title="Senior Backend Engineer",
            company="Example Co",
            location="Sydney NSW",
            job_url="https://www.seek.com.au/job/1",
            summary=None,
            match_score=0.92,
            discovered_at="2026-04-17T00:05:00+00:00",
            first_seen_at="2026-04-17T00:05:00+00:00",
            last_seen_at="2026-04-17T00:05:00+00:00",
            is_new=True,
            status="new",
        ),
        DiscoveredJobRecord(
            job_key="seek:https://www.seek.com.au/job/2",
            source="seek",
            resume_language="en",
            title="Platform Engineer",
            company="Example Co",
            location="Sydney NSW",
            job_url="https://www.seek.com.au/job/2",
            summary=None,
            match_score=0.83,
            discovered_at="2026-04-17T00:05:00+00:00",
            first_seen_at="2026-04-17T00:05:00+00:00",
            last_seen_at="2026-04-17T00:05:00+00:00",
            is_new=True,
            status="applied",
        ),
        DiscoveredJobRecord(
            job_key="seek:https://www.seek.com.au/job/3",
            source="seek",
            resume_language="en",
            title="Backend Engineer",
            company="Other Co",
            location="Sydney NSW",
            job_url="https://www.seek.com.au/job/3",
            summary=None,
            match_score=0.61,
            discovered_at="2026-04-17T00:05:00+00:00",
            first_seen_at="2026-04-17T00:05:00+00:00",
            last_seen_at="2026-04-17T00:05:00+00:00",
            is_new=True,
            status="new",
        ),
    ]

    filtered = filter_high_score_unapplied_jobs(jobs, threshold=0.75)

    assert [job.job_key for job in filtered] == ["seek:https://www.seek.com.au/job/1"]


def test_mark_job_status_updates_existing_record():
    existing = {
        "seek:https://www.seek.com.au/job/1": {
            "job_key": "seek:https://www.seek.com.au/job/1",
            "source": "seek",
            "resume_language": "en",
            "title": "Senior Backend Engineer",
            "company": "Example Co",
            "location": "Sydney NSW",
            "job_url": "https://www.seek.com.au/job/1",
            "summary": None,
            "match_score": 0.92,
            "discovered_at": "2026-04-17T00:05:00+00:00",
            "first_seen_at": "2026-04-17T00:05:00+00:00",
            "last_seen_at": "2026-04-17T00:05:00+00:00",
            "is_new": True,
            "status": "new",
        }
    }

    with patch("app.career_ops.scheduled_scan.db.get_discovered_jobs_map", return_value=existing), patch(
        "app.career_ops.scheduled_scan.db.upsert_discovered_jobs"
    ) as mock_upsert:
        record = mark_job_status("seek:https://www.seek.com.au/job/1", "applied")

    assert record.status == "applied"
    saved_record = mock_upsert.call_args.args[0][0]
    assert saved_record["status"] == "applied"
