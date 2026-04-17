"""Live market-data helpers for Career Ops Block D."""

from __future__ import annotations

import logging
import re
from html import unescape
from urllib.parse import quote_plus

import httpx

from app.schemas.models import CareerOpsMarketData, CareerOpsMarketSource

logger = logging.getLogger(__name__)

_SALARY_PATTERN = re.compile(
    r"(?:(?:\$|USD)\s?\d[\d,]*(?:\.\d+)?(?:K|M)?)\s*(?:-|to)\s*(?:(?:\$|USD)\s?\d[\d,]*(?:\.\d+)?(?:K|M)?)|(?:\$|USD)\s?\d[\d,]*(?:\.\d+)?(?:K|M)?",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


def build_market_search_queries(role_query: str, company_name: str | None = None) -> list[str]:
    """Build live market-search queries."""
    queries = [f'{role_query.strip()} salary levels.fyi Glassdoor salary.com']
    if company_name:
        queries.append(f'{company_name.strip()} compensation salary reviews {role_query.strip()}')
    else:
        queries.append(f'{role_query.strip()} compensation benchmark')
    queries.append(f'{role_query.strip()} hiring demand market trend 2026')
    return queries


def extract_salary_mentions(text: str) -> list[str]:
    """Extract salary mentions from unstructured text."""
    mentions: list[str] = []
    for match in _SALARY_PATTERN.finditer(text):
        value = match.group(0).strip()
        if value not in mentions:
            mentions.append(value)
    return mentions


def parse_duckduckgo_results(html: str) -> list[dict[str, str]]:
    """Parse DuckDuckGo HTML results into title/url/snippet records."""
    title_matches = re.findall(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    snippet_matches = re.findall(
        r'<a[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</a>|<div[^>]+class="[^"]*result__snippet[^"]*"[^>]*>(.*?)</div>',
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )

    results: list[dict[str, str]] = []
    for index, (url, raw_title) in enumerate(title_matches):
        raw_snippet = ""
        if index < len(snippet_matches):
            raw_snippet = next((item for item in snippet_matches[index] if item), "")
        results.append(
            {
                "title": unescape(_TAG_RE.sub("", raw_title)).strip(),
                "url": unescape(url).strip(),
                "snippet": unescape(_TAG_RE.sub("", raw_snippet)).strip(),
            }
        )
    return results


async def fetch_market_signals(
    role_query: str,
    company_name: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> CareerOpsMarketData:
    """Fetch live salary/demand hints from public search results."""
    queries = build_market_search_queries(role_query, company_name=company_name)
    owns_client = client is None
    client = client or httpx.AsyncClient(timeout=15.0, follow_redirects=True)

    try:
        seen_urls: set[str] = set()
        salary_mentions: list[str] = []
        sources: list[CareerOpsMarketSource] = []

        for query in queries:
            response = await client.get(
                f"https://duckduckgo.com/html/?q={quote_plus(query)}",
                headers={"User-Agent": "Mozilla/5.0"},
            )
            response.raise_for_status()
            for item in parse_duckduckgo_results(response.text)[:3]:
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                sources.append(CareerOpsMarketSource(**item))
                for mention in extract_salary_mentions(item["snippet"]):
                    if mention not in salary_mentions:
                        salary_mentions.append(mention)

        return CareerOpsMarketData(
            role_query=role_query,
            company_name=company_name,
            salary_mentions=salary_mentions,
            demand_summary=(
                f"Collected {len(sources)} live search results for demand and compensation signals."
                if sources
                else "No live demand results were found."
            ),
            compensation_summary=(
                "Salary mentions found: " + ", ".join(salary_mentions[:3])
                if salary_mentions
                else "No explicit salary numbers were found in live search snippets."
            ),
            sources=sources[:6],
        )
    except Exception as exc:
        logger.warning("Live market-data lookup failed: %s", exc)
        return CareerOpsMarketData(
            role_query=role_query,
            company_name=company_name,
            demand_summary="Live market lookup failed.",
            compensation_summary="Live market lookup failed.",
            salary_mentions=[],
            sources=[],
        )
    finally:
        if owns_client:
            await client.aclose()
