from __future__ import annotations

import asyncio
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus, urljoin

from playwright.async_api import async_playwright

from app.ai.tasks import generate_search_queries, to_seek_search_plan
from app.database import db
from app.schemas.models import (
    ResumeData,
    SeekManualSearchResponse,
    SeekRawJob,
    SeekSearchError,
    SeekSearchJob,
    SeekSearchPlan,
    SeekSearchStats,
)


DEFAULT_SEEK_LOCATION = "Sydney NSW"


def _resume_text(resume: ResumeData) -> str:
    parts: list[str] = [resume.summary or ""]
    for entry in resume.workExperience:
        parts.extend(entry.description)
        parts.append(entry.title)
    parts.extend(resume.additional.technicalSkills)
    return " ".join(part for part in parts if part).lower()
async def build_seek_search_plan(
    resume: ResumeData,
    *,
    resume_id: str,
    location: str = DEFAULT_SEEK_LOCATION,
) -> SeekSearchPlan:
    generated_queries = await generate_search_queries(
        resume=resume,
        language="en",
        default_location=location,
    )
    plan = to_seek_search_plan(
        generated_queries,
        resume_id=resume_id,
        source="seek",
    )
    return plan.model_copy(update={"location": location})


def build_seek_search_url(*, keyword: str, location: str) -> str:
    normalized_location = location.strip().replace(",", "")
    return (
        f"https://www.seek.com.au/{quote_plus(keyword)}/jobs"
        f"?where={quote_plus(normalized_location)}"
    )


class _SeekListHTMLParser(HTMLParser):
    def __init__(self, *, base_url: str, search_keyword: str):
        super().__init__()
        self.base_url = base_url
        self.search_keyword = search_keyword
        self.jobs: list[SeekRawJob] = []
        self._inside_card = False
        self._current: dict[str, str] | None = None
        self._field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        automation = attr_map.get("data-automation", "")
        if automation == "normalJob":
            self._inside_card = True
            self._current = {"search_keyword": self.search_keyword}
            self._field = None
            return

        if not self._inside_card or self._current is None:
            return

        if automation == "jobTitle":
            self._field = "title"
            href = attr_map.get("href", "")
            if href:
                self._current["job_url"] = urljoin(self.base_url, href)
            return

        field_map = {
            "jobCompany": "company",
            "jobLocation": "location",
            "jobSalary": "salary",
            "jobWorkType": "work_type",
            "jobListingDate": "listed_at",
            "jobShortDescription": "summary",
        }
        if automation in field_map:
            self._field = field_map[automation]

    def handle_data(self, data: str) -> None:
        if not self._inside_card or not self._field or self._current is None:
            return
        text = data.strip()
        if not text:
            return
        existing = self._current.get(self._field, "")
        self._current[self._field] = f"{existing} {text}".strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "article" and self._inside_card and self._current is not None:
            if self._current.get("title") and self._current.get("company"):
                self.jobs.append(SeekRawJob.model_validate(self._current))
            self._inside_card = False
            self._current = None
            self._field = None


def parse_seek_list_html(
    html: str,
    *,
    base_url: str,
    search_keyword: str,
) -> list[SeekRawJob]:
    parser = _SeekListHTMLParser(base_url=base_url, search_keyword=search_keyword)
    parser.feed(html)
    return parser.jobs


def dedupe_seek_jobs(jobs: list[SeekRawJob]) -> list[SeekRawJob]:
    seen: set[str] = set()
    result: list[SeekRawJob] = []
    for job in jobs:
        key = job.job_url or f"{job.title}|{job.company}|{job.location}"
        if key in seen:
            continue
        seen.add(key)
        result.append(job)
    return result


def score_seek_job(job: SeekRawJob, resume: ResumeData, *, location: str) -> float:
    haystack = f"{job.title} {job.summary or ''}".lower()
    resume_text = _resume_text(resume)
    score = 0.0

    for keyword in ("python", "backend", "fastapi", "aws", "platform"):
        if keyword in haystack and keyword in resume_text:
            score += 0.18

    if location.strip().lower() and location.strip().lower() in (job.location or "").lower():
        score += 0.2

    if "senior" in haystack and "senior" in resume_text:
        score += 0.1

    return min(round(score, 4), 1.0)


def normalize_seek_jobs(
    jobs: list[SeekRawJob],
    *,
    resume: ResumeData,
    location: str,
) -> list[SeekSearchJob]:
    normalized: list[SeekSearchJob] = []
    for job in dedupe_seek_jobs(jobs):
        match_score = score_seek_job(job, resume, location=location)
        normalized.append(
            SeekSearchJob(
                job_id=f"seek:{job.job_url or f'{job.title}|{job.company}|{job.location}'}",
                source="seek",
                search_keyword=job.search_keyword,
                title=job.title,
                company=job.company,
                location=job.location,
                salary=job.salary,
                work_type=job.work_type,
                listed_at=job.listed_at,
                job_url=job.job_url,
                summary=job.summary,
                match_score=match_score,
            )
        )
    return sorted(normalized, key=lambda item: item.match_score, reverse=True)


async def scrape_seek_search_results(*, keyword: str, location: str) -> list[SeekRawJob]:
    url = build_seek_search_url(keyword=keyword, location=location)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)
            html = await page.content()
        finally:
            await browser.close()
    return parse_seek_list_html(html, base_url="https://www.seek.com.au", search_keyword=keyword)


async def scrape_seek_keywords_concurrently(
    *,
    keywords: list[str],
    location: str,
) -> tuple[list[SeekRawJob], list[SeekSearchError], int]:
    async def scrape_keyword(keyword: str) -> tuple[list[SeekRawJob], SeekSearchError | None]:
        try:
            results = await scrape_seek_search_results(keyword=keyword, location=location)
            return results, None
        except Exception as exc:
            return [], SeekSearchError(search_keyword=keyword, message=str(exc))

    results = await asyncio.gather(*(scrape_keyword(keyword) for keyword in keywords))
    raw_jobs: list[SeekRawJob] = []
    errors: list[SeekSearchError] = []

    for jobs, error in results:
        raw_jobs.extend(jobs)
        if error:
            errors.append(error)

    return raw_jobs, errors, len(keywords) - len(errors)


def _resume_from_record(resume_record: dict[str, Any]) -> ResumeData:
    processed = resume_record.get("processed_data") or {}
    return ResumeData.model_validate(processed)


async def run_manual_seek_search(
    *,
    resume_id: str,
    location: str | None = None,
) -> SeekManualSearchResponse:
    resume_record = db.get_resume(resume_id)
    if not resume_record:
        raise ValueError(f"Resume not found: {resume_id}")

    resume = _resume_from_record(resume_record)
    plan = await build_seek_search_plan(
        resume,
        resume_id=resume_id,
        location=location or DEFAULT_SEEK_LOCATION,
    )

    raw_jobs, errors, queries_succeeded = await scrape_seek_keywords_concurrently(
        keywords=plan.keywords,
        location=plan.location,
    )

    jobs = normalize_seek_jobs(raw_jobs, resume=resume, location=plan.location)
    stats = SeekSearchStats(
        keywords_generated=len(plan.keywords),
        queries_attempted=len(plan.keywords),
        queries_succeeded=queries_succeeded,
        raw_jobs_found=len(raw_jobs),
        jobs_after_dedupe=len(jobs),
    )
    return SeekManualSearchResponse(plan=plan, jobs=jobs, stats=stats, errors=errors)
