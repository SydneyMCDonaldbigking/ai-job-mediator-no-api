from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.schemas.models import SeekRawJob


BRAVE_WEB_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
TAVILY_SEARCH_URL = "https://api.tavily.com/search"


def get_search_fallback_provider() -> str:
    provider = settings.job_search_fallback_provider.strip().lower()
    if provider == "auto":
        if settings.tavily_api_key.strip():
            return "tavily"
        if settings.brave_search_api_key.strip():
            return "brave"
        return "disabled"
    return provider


def is_search_fallback_configured() -> bool:
    provider = get_search_fallback_provider()
    if provider == "tavily":
        return bool(settings.tavily_api_key.strip())
    if provider == "brave":
        return bool(settings.brave_search_api_key.strip())
    return False


def build_job_search_query(*, source: str, keyword: str, location: str) -> str:
    normalized_source = source.strip().lower()
    terms = " ".join(part for part in (keyword.strip(), location.strip()) if part)
    if normalized_source == "seek":
        return f"site:seek.com.au/job {terms}".strip()
    if normalized_source == "doda":
        return f"site:doda.jp/DodaFront/View/JobSearchDetail {terms}".strip()
    raise ValueError(f"Unsupported job search source: {source}")


def _is_supported_job_url(*, source: str, url: str) -> bool:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path
    if source == "seek":
        return host.endswith("seek.com.au") and (
            path.startswith("/job/") or path.endswith("-jobs") or "-jobs/" in path
        )
    if source == "doda":
        return host.endswith("doda.jp") and "/DodaFront/View/JobSearchDetail/" in path
    return False


def _normalize_result_url(url: str) -> str:
    parsed = urlparse(url.strip())
    return parsed._replace(fragment="").geturl()


def _clean_search_title(title: str, *, source: str) -> tuple[str, str]:
    normalized = " ".join(title.split())
    if source == "seek":
        cleaned = re.sub(r"\s*[|｜-]\s*SEEK.*$", "", normalized, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s+Jobs in .*$", " Jobs", cleaned, flags=re.IGNORECASE)
        return cleaned or "SEEK job search", "SEEK"

    cleaned = re.sub(r"\s*[-－]\s*転職ならdoda.*$", "", normalized)
    cleaned = re.sub(r"\s*の求人情報.*$", "", cleaned)
    for separator in ("／", "/"):
        if separator in cleaned:
            company, job_title = cleaned.split(separator, 1)
            return job_title.strip() or cleaned, company.strip() or "doda"
    return cleaned or "doda job", "doda"


def raw_jobs_from_web_results(
    results: list[dict[str, object]],
    *,
    source: str,
    search_keyword: str,
    location: str,
) -> list[SeekRawJob]:
    normalized_source = source.strip().lower()
    jobs: list[SeekRawJob] = []
    seen_urls: set[str] = set()
    for result in results:
        raw_url = str(result.get("url") or "")
        url = _normalize_result_url(raw_url)
        if not url or url in seen_urls:
            continue
        if not _is_supported_job_url(source=normalized_source, url=url):
            continue
        title, company = _clean_search_title(
            str(result.get("title") or ""),
            source=normalized_source,
        )
        summary = str(result.get("description") or result.get("content") or "") or None
        jobs.append(
            SeekRawJob(
                search_keyword=search_keyword,
                title=title,
                company=company,
                location=location,
                job_url=url,
                summary=summary,
            )
        )
        seen_urls.add(url)
    return jobs


async def search_jobs_via_fallback(
    *,
    source: str,
    keyword: str,
    location: str,
    count: int | None = None,
) -> list[SeekRawJob]:
    provider = get_search_fallback_provider()
    if provider == "tavily":
        return await _search_jobs_via_tavily(
            source=source,
            keyword=keyword,
            location=location,
            count=count,
        )
    if provider == "brave":
        return await _search_jobs_via_brave(
            source=source,
            keyword=keyword,
            location=location,
            count=count,
        )
    return []


async def _search_jobs_via_brave(
    *,
    source: str,
    keyword: str,
    location: str,
    count: int | None = None,
) -> list[SeekRawJob]:
    api_key = settings.brave_search_api_key.strip()
    if not api_key:
        return []

    normalized_source = source.strip().lower()
    query = build_job_search_query(
        source=normalized_source,
        keyword=keyword,
        location=location,
    )
    country = "au" if normalized_source == "seek" else "jp"
    search_lang = "en" if normalized_source == "seek" else "ja"
    requested_count = count or settings.job_search_fallback_count

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            BRAVE_WEB_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query,
                "count": requested_count,
                "country": country,
                "search_lang": search_lang,
            },
        )
    response.raise_for_status()
    payload = response.json()
    web_results = (payload.get("web") or {}).get("results") or []
    return raw_jobs_from_web_results(
        web_results,
        source=normalized_source,
        search_keyword=keyword,
        location=location,
    )


async def _search_jobs_via_tavily(
    *,
    source: str,
    keyword: str,
    location: str,
    count: int | None = None,
) -> list[SeekRawJob]:
    api_key = settings.tavily_api_key.strip()
    if not api_key:
        return []

    normalized_source = source.strip().lower()
    query = build_job_search_query(
        source=normalized_source,
        keyword=keyword,
        location=location,
    )
    country = "australia" if normalized_source == "seek" else "japan"
    include_domains = ["seek.com.au"] if normalized_source == "seek" else ["doda.jp"]
    requested_count = count or settings.job_search_fallback_count

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            TAVILY_SEARCH_URL,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "search_depth": settings.tavily_search_depth,
                "max_results": requested_count,
                "topic": "general",
                "country": country,
                "include_domains": include_domains,
                "include_answer": False,
                "include_raw_content": False,
                "include_images": False,
                "auto_parameters": False,
            },
        )
    response.raise_for_status()
    payload = response.json()
    web_results = payload.get("results") or []
    return raw_jobs_from_web_results(
        web_results,
        source=normalized_source,
        search_keyword=keyword,
        location=location,
    )
