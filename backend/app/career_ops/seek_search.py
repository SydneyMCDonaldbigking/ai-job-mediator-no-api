from __future__ import annotations

import asyncio
import json
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote, urljoin, urlparse

from playwright.async_api import async_playwright

from app.ai.tasks import generate_search_queries, to_seek_search_plan
from app.career_ops.search_fallback import (
    is_search_fallback_configured,
    search_jobs_via_fallback,
)
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
SEEK_DETAIL_FETCH_LIMIT = 5


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
    keyword_slug = "-".join(part for part in re.split(r"\s+", keyword.strip()) if part)
    location_slug = "-".join(
        part for part in re.split(r"[\s,]+", location.strip()) if part
    )
    return (
        "https://www.seek.com.au/"
        f"{quote(keyword_slug, safe='-')}-jobs/in-{quote(location_slug, safe='-')}"
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


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)

    def get_text(self) -> str:
        return " ".join(self.parts)


def _strip_html_text(value: str) -> str:
    parser = _HTMLTextExtractor()
    parser.feed(unescape(value))
    text = parser.get_text() or unescape(value)
    return re.sub(r"\s+", " ", text).strip()


class _SeekDetailHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ld_json_scripts: list[str] = []
        self.detail_parts: list[str] = []
        self._inside_ld_json = False
        self._inside_detail = False
        self._detail_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "script" and "ld+json" in attr_map.get("type", "").lower():
            self._inside_ld_json = True
            return

        automation = attr_map.get("data-automation", "")
        if automation in {"jobAdDetails", "jobDescription", "jobDescriptionText"}:
            self._inside_detail = True
            self._detail_depth = 1
            return

        if self._inside_detail:
            self._detail_depth += 1

    def handle_data(self, data: str) -> None:
        if self._inside_ld_json:
            self.ld_json_scripts.append(data)
            return
        if self._inside_detail:
            text = data.strip()
            if text:
                self.detail_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._inside_ld_json:
            self._inside_ld_json = False
            return
        if self._inside_detail:
            self._detail_depth -= 1
            if self._detail_depth <= 0:
                self._inside_detail = False
                self._detail_depth = 0


def _json_ld_job_description(payload: Any) -> str | None:
    if isinstance(payload, list):
        for item in payload:
            description = _json_ld_job_description(item)
            if description:
                return description
        return None

    if not isinstance(payload, dict):
        return None

    node_type = payload.get("@type")
    node_types = node_type if isinstance(node_type, list) else [node_type]
    if any(str(item).lower() == "jobposting" for item in node_types):
        description = payload.get("description")
        if isinstance(description, str) and description.strip():
            return _strip_html_text(description)

    for value in payload.values():
        description = _json_ld_job_description(value)
        if description:
            return description
    return None


def parse_seek_detail_html(html: str) -> str | None:
    parser = _SeekDetailHTMLParser()
    parser.feed(html)

    for script in parser.ld_json_scripts:
        try:
            payload = json.loads(script.strip())
        except json.JSONDecodeError:
            continue
        description = _json_ld_job_description(payload)
        if description:
            return description

    detail_text = re.sub(r"\s+", " ", " ".join(parser.detail_parts)).strip()
    return detail_text or None


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
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status >= 400:
                raise RuntimeError(f"SEEK returned HTTP {response.status} for {url}")
            await page.wait_for_timeout(1000)
            html = await page.content()
        finally:
            await browser.close()
    return parse_seek_list_html(html, base_url="https://www.seek.com.au", search_keyword=keyword)


def _is_seek_detail_job_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.lower().endswith("seek.com.au") and parsed.path.startswith("/job/")


async def scrape_seek_job_detail(url: str) -> str | None:
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            if response and response.status >= 400:
                raise RuntimeError(f"SEEK returned HTTP {response.status} for {url}")
            await page.wait_for_timeout(1000)
            html = await page.content()
        finally:
            await browser.close()
    return parse_seek_detail_html(html)


async def enrich_seek_jobs_with_details(
    jobs: list[SeekRawJob],
    *,
    detail_limit: int = SEEK_DETAIL_FETCH_LIMIT,
) -> list[SeekRawJob]:
    if detail_limit <= 0:
        return jobs

    enriched = list(jobs)
    semaphore = asyncio.Semaphore(2)

    async def enrich_one(index: int, job: SeekRawJob) -> tuple[int, SeekRawJob]:
        async with semaphore:
            try:
                detail = await scrape_seek_job_detail(job.job_url)
            except Exception:
                return index, job
        if not detail:
            return index, job
        current_summary = (job.summary or "").strip()
        if len(detail) <= len(current_summary):
            return index, job
        return index, job.model_copy(update={"summary": detail})

    tasks = []
    for index, job in enumerate(jobs):
        if len(tasks) >= detail_limit:
            break
        if _is_seek_detail_job_url(job.job_url):
            tasks.append(enrich_one(index, job))

    if not tasks:
        return enriched

    for index, job in await asyncio.gather(*tasks):
        enriched[index] = job
    return enriched


async def scrape_seek_keywords_concurrently(
    *,
    keywords: list[str],
    location: str,
) -> tuple[list[SeekRawJob], list[SeekSearchError], int]:
    async def scrape_keyword(keyword: str) -> tuple[list[SeekRawJob], SeekSearchError | None]:
        direct_error: str | None = None
        try:
            results = await scrape_seek_search_results(keyword=keyword, location=location)
            if results:
                return results, None
            direct_error = "No SEEK jobs parsed from the search page."
        except Exception as exc:
            direct_error = str(exc).strip() or exc.__class__.__name__

        if is_search_fallback_configured():
            try:
                fallback_results = await search_jobs_via_fallback(
                    source="seek",
                    keyword=keyword,
                    location=location,
                )
            except Exception as exc:
                fallback_error = str(exc).strip() or exc.__class__.__name__
                return [], SeekSearchError(
                    search_keyword=keyword,
                    message=f"{direct_error}; search fallback failed: {fallback_error}",
                )
            if fallback_results:
                return fallback_results, None
            direct_error = f"{direct_error}; search fallback returned no SEEK job links."

        return [], SeekSearchError(search_keyword=keyword, message=direct_error)

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

    raw_jobs_found = len(raw_jobs)
    raw_jobs = await enrich_seek_jobs_with_details(raw_jobs)
    jobs = normalize_seek_jobs(raw_jobs, resume=resume, location=plan.location)
    stats = SeekSearchStats(
        keywords_generated=len(plan.keywords),
        queries_attempted=len(plan.keywords),
        queries_succeeded=queries_succeeded,
        raw_jobs_found=raw_jobs_found,
        jobs_after_dedupe=len(jobs),
    )
    return SeekManualSearchResponse(plan=plan, jobs=jobs, stats=stats, errors=errors)
