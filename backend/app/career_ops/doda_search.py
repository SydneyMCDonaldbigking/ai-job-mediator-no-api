from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import quote_plus, urljoin

from playwright.async_api import async_playwright

from app.ai.tasks import generate_search_queries, to_seek_search_plan
from app.career_ops.seek_search import _resume_from_record, _resume_text, score_seek_job
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


DEFAULT_DODA_LOCATION = "東京"


def localize_location_for_doda(*, country: str, location_text: str) -> str:
    mapping = {
        ("JP", "Tokyo"): "東京",
        ("JP", "Osaka"): "大阪",
        ("JP", "Kyoto"): "京都",
        ("JP", "Nagoya"): "名古屋",
    }
    normalized_country = country.strip().upper()
    normalized_location = location_text.strip()
    if normalized_country == "JP":
        english_city_aliases = {
            "tokyo": "Tokyo",
            "osaka": "Osaka",
            "kyoto": "Kyoto",
            "nagoya": "Nagoya",
        }
        normalized_location = english_city_aliases.get(
            normalized_location.casefold(),
            normalized_location,
        )
    return mapping.get((normalized_country, normalized_location), normalized_location)


def _build_doda_search_plan_fallback(
    resume: ResumeData,
    *,
    resume_id: str,
    country: str = "JP",
    location_text: str = DEFAULT_DODA_LOCATION,
) -> SeekSearchPlan:
    text = _resume_text(resume)
    keywords: list[str] = []

    if "backend" in text or "api" in text:
        keywords.append("バックエンドエンジニア")
    if "python" in text:
        keywords.append("python エンジニア")
    if "aws" in text or "platform" in text:
        keywords.append("プラットフォームエンジニア")
    if "fastapi" in text:
        keywords.append("python バックエンド")
    if not keywords:
        keywords.append("ソフトウェアエンジニア")

    return SeekSearchPlan(
        resume_id=resume_id,
        source="doda",
        candidate_profile_summary=resume.summary or "Japanese candidate resume profile",
        keywords=list(dict.fromkeys(keywords)),
        location=localize_location_for_doda(country=country, location_text=location_text),
    )


async def build_doda_search_plan(
    resume: ResumeData,
    *,
    resume_id: str,
    country: str = "JP",
    location_text: str = DEFAULT_DODA_LOCATION,
) -> SeekSearchPlan:
    localized = localize_location_for_doda(country=country, location_text=location_text)
    generated_queries = await generate_search_queries(
        resume=resume,
        language="ja",
        default_location=localized,
    )
    plan = to_seek_search_plan(
        generated_queries,
        resume_id=resume_id,
        source="doda",
    )
    return plan.model_copy(update={"location": localized})


def build_doda_search_url(*, keyword: str, location: str) -> str:
    query = quote_plus(keyword)
    area = quote_plus(location)
    return (
        "https://doda.jp/DodaFront/View/JobSearchList/"
        f"-kw__{query}/-pr__13/-ar__3/-ci__{area}/"
    )


class _DodaListHTMLParser(HTMLParser):
    def __init__(self, *, base_url: str, search_keyword: str):
        super().__init__()
        self.base_url = base_url
        self.search_keyword = search_keyword
        self.jobs: list[SeekRawJob] = []
        self._inside_card = False
        self._current: dict[str, Any] | None = None
        self._field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        classes = attr_map.get("class", "")
        if "jobCard" in classes:
            self._inside_card = True
            self._current = {"search_keyword": self.search_keyword, "is_new": False}
            self._field = None
            return

        if not self._inside_card or self._current is None:
            return

        class_map = {
            "jobTitle": "title",
            "companyName": "company",
            "workLocation": "location",
            "salaryText": "salary",
            "jobDescription": "summary",
        }
        for class_name, field in class_map.items():
            if class_name in classes:
                self._field = field
                break
        else:
            self._field = None

        if tag == "a" and "jobLink" in classes:
            href = attr_map.get("href", "")
            if href:
                self._current["job_url"] = urljoin(self.base_url, href)

        if "newMarker" in classes:
            self._current["is_new"] = True

    def handle_data(self, data: str) -> None:
        if not self._inside_card or not self._field or self._current is None:
            return
        text = data.strip()
        if not text:
            return
        existing = self._current.get(self._field, "")
        self._current[self._field] = f"{existing} {text}".strip()

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._inside_card and self._current is not None and self._current.get("title") and self._current.get("company"):
            self.jobs.append(SeekRawJob.model_validate(self._current))
            self._inside_card = False
            self._current = None
            self._field = None


def parse_doda_list_html(
    html: str,
    *,
    base_url: str,
    search_keyword: str,
) -> list[SeekRawJob]:
    parser = _DodaListHTMLParser(base_url=base_url, search_keyword=search_keyword)
    parser.feed(html)
    return parser.jobs


def normalize_doda_job(raw_job: dict[str, Any] | SeekRawJob) -> SeekSearchJob:
    job = raw_job if isinstance(raw_job, SeekRawJob) else SeekRawJob.model_validate(raw_job)
    stable_key = job.job_url or f"{job.title}|{job.company}|{job.location}"
    return SeekSearchJob(
        job_id=f"doda:{stable_key}",
        source="doda",
        language="ja",
        search_keyword=job.search_keyword,
        title=job.title,
        company=job.company,
        location=job.location,
        salary=job.salary,
        work_type=job.work_type,
        listed_at=job.listed_at,
        job_url=job.job_url,
        summary=job.summary,
        raw_location_text=job.location,
        raw_salary_text=job.salary,
        match_score=0.0,
    )


def normalize_doda_jobs(
    jobs: list[SeekRawJob],
    *,
    resume: ResumeData,
    location: str,
) -> list[SeekSearchJob]:
    seen: set[str] = set()
    normalized: list[SeekSearchJob] = []
    for job in jobs:
        key = job.job_url or f"{job.title}|{job.company}|{job.location}"
        if key in seen:
            continue
        seen.add(key)
        normalized_job = normalize_doda_job(job)
        normalized_job.match_score = score_seek_job(job, resume, location=location)
        normalized.append(normalized_job)
    return sorted(normalized, key=lambda item: item.match_score, reverse=True)


async def scrape_doda_search_results(*, keyword: str, location: str) -> list[SeekRawJob]:
    url = build_doda_search_url(keyword=keyword, location=location)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)
            html = await page.content()
        finally:
            await browser.close()
    return parse_doda_list_html(html, base_url="https://doda.jp", search_keyword=keyword)


async def run_manual_doda_search(
    *,
    resume_id: str,
    location: str | None = None,
) -> SeekManualSearchResponse:
    resume_record = db.get_resume(resume_id)
    if not resume_record:
        raise ValueError(f"Resume not found: {resume_id}")

    resume = _resume_from_record(resume_record)
    plan = await build_doda_search_plan(
        resume,
        resume_id=resume_id,
        location_text=location or DEFAULT_DODA_LOCATION,
    )

    raw_jobs: list[SeekRawJob] = []
    errors: list[SeekSearchError] = []
    queries_succeeded = 0

    for keyword in plan.keywords:
        try:
            results = await scrape_doda_search_results(keyword=keyword, location=plan.location)
            raw_jobs.extend(results)
            queries_succeeded += 1
        except Exception as exc:
            errors.append(SeekSearchError(search_keyword=keyword, message=str(exc)))

    jobs = normalize_doda_jobs(raw_jobs, resume=resume, location=plan.location)
    stats = SeekSearchStats(
        keywords_generated=len(plan.keywords),
        queries_attempted=len(plan.keywords),
        queries_succeeded=queries_succeeded,
        raw_jobs_found=len(raw_jobs),
        jobs_after_dedupe=len(jobs),
    )
    return SeekManualSearchResponse(plan=plan, jobs=jobs, stats=stats, errors=errors)
