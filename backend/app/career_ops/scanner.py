"""Python-native portal scanner inspired by ``career-ops/scan.mjs``."""

from __future__ import annotations

import asyncio
import csv
import logging
import shutil
from pathlib import Path
from typing import Any, Callable

import httpx
import yaml

from app.config import settings
from app.schemas.models import CareerOpsScanData, CareerOpsScannedOffer, PortalsConfig

logger = logging.getLogger(__name__)


def ensure_portals_config(
    config_path: Path | None = None,
    example_path: Path | None = None,
) -> Path:
    """Create ``portals.yml`` from the bundled example when missing."""
    config_path = config_path or settings.portals_config_path
    example_path = example_path or settings.portals_example_path
    config_path.parent.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        if not example_path.exists():
            raise FileNotFoundError(f"Portals example file not found: {example_path}")
        shutil.copyfile(example_path, config_path)
    return config_path


def load_portals_config(config_path: Path | None = None) -> dict[str, Any]:
    """Load and validate the active portals configuration."""
    path = ensure_portals_config(config_path=config_path)
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PortalsConfig.model_validate(payload).model_dump()


def save_portals_config(config: dict[str, Any], config_path: Path | None = None) -> dict[str, Any]:
    """Validate and write the portals configuration to YAML."""
    normalized = PortalsConfig.model_validate(config)
    path = config_path or settings.portals_config_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            normalized.model_dump(exclude_none=True),
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    return normalized.model_dump()


def detect_api(company: dict[str, Any]) -> dict[str, str] | None:
    """Infer the ATS API endpoint for a tracked company."""
    explicit_api = str(company.get("api", "")).strip()
    if "greenhouse" in explicit_api:
        return {"type": "greenhouse", "url": explicit_api}

    careers_url = str(company.get("careers_url", "")).strip()
    if "jobs.ashbyhq.com/" in careers_url:
        slug = careers_url.rstrip("/").split("/")[-1]
        return {
            "type": "ashby",
            "url": f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
        }
    if "jobs.lever.co/" in careers_url:
        slug = careers_url.rstrip("/").split("/")[-1]
        return {"type": "lever", "url": f"https://api.lever.co/v0/postings/{slug}"}
    if "greenhouse.io/" in careers_url:
        slug = careers_url.rstrip("/").split("/")[-1]
        return {
            "type": "greenhouse",
            "url": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        }
    return None


def build_title_filter(title_filter: dict[str, Any]) -> Callable[[str], bool]:
    """Build the title matcher from positive/negative keywords."""
    positives = [
        str(item).lower()
        for item in title_filter.get("positive", [])
        if str(item).strip()
    ]
    negatives = [
        str(item).lower()
        for item in title_filter.get("negative", [])
        if str(item).strip()
    ]

    def matches(title: str) -> bool:
        lower = title.lower()
        has_positive = not positives or any(keyword in lower for keyword in positives)
        has_negative = any(keyword in lower for keyword in negatives)
        return has_positive and not has_negative

    return matches


def parse_greenhouse_jobs(payload: dict[str, Any], company_name: str) -> list[dict[str, str]]:
    """Normalize Greenhouse jobs payload."""
    return [
        {
            "title": str(item.get("title", "")),
            "url": str(item.get("absolute_url", "")),
            "company": company_name,
            "location": str(item.get("location", {}).get("name", "")),
            "source": "greenhouse",
        }
        for item in payload.get("jobs", [])
    ]


def parse_ashby_jobs(payload: dict[str, Any], company_name: str) -> list[dict[str, str]]:
    """Normalize Ashby jobs payload."""
    return [
        {
            "title": str(item.get("title", "")),
            "url": str(item.get("jobUrl", "")),
            "company": company_name,
            "location": str(item.get("location", "")),
            "source": "ashby",
        }
        for item in payload.get("jobs", [])
    ]


def parse_lever_jobs(payload: list[dict[str, Any]], company_name: str) -> list[dict[str, str]]:
    """Normalize Lever jobs payload."""
    return [
        {
            "title": str(item.get("text", "")),
            "url": str(item.get("hostedUrl", "")),
            "company": company_name,
            "location": str(item.get("categories", {}).get("location", "")),
            "source": "lever",
        }
        for item in payload
    ]


_PARSERS = {
    "greenhouse": parse_greenhouse_jobs,
    "ashby": parse_ashby_jobs,
    "lever": parse_lever_jobs,
}


def _load_seen_urls(history_path: Path | None = None) -> set[str]:
    path = history_path or settings.scan_history_path
    if not path.exists():
        return set()

    seen: set[str] = set()
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            url = str(row.get("url", "")).strip()
            if url:
                seen.add(url)
    return seen


def _append_history(
    offers: list[CareerOpsScannedOffer],
    history_path: Path | None = None,
) -> None:
    path = history_path or settings.scan_history_path
    path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path.exists()

    with path.open("a", encoding="utf-8", newline="") as handle:
        fieldnames = ["url", "portal", "title", "company", "status"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        if not file_exists:
            writer.writeheader()
        for offer in offers:
            writer.writerow(
                {
                    "url": offer.url,
                    "portal": offer.source,
                    "title": offer.title,
                    "company": offer.company,
                    "status": "added",
                }
            )


async def scan_portals(
    *,
    config: dict[str, Any] | None = None,
    limit_companies: int | None = None,
    history_path: Path | None = None,
) -> CareerOpsScanData:
    """Scan configured ATS APIs and return matching new offers."""
    config = config or load_portals_config()
    matcher = build_title_filter(config.get("title_filter", {}))
    companies = [
        company
        for company in config.get("tracked_companies", [])
        if company.get("enabled", True)
    ]
    if limit_companies is not None:
        companies = companies[:limit_companies]

    seen_urls = _load_seen_urls(history_path=history_path)
    total_jobs_found = 0
    filtered_out = 0
    duplicates = 0
    errors: list[str] = []
    new_offers: list[CareerOpsScannedOffer] = []

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        async def fetch_company_jobs(
            company: dict[str, Any],
        ) -> tuple[str, list[dict[str, str]], str | None]:
            api_info = detect_api(company)
            company_name = str(company.get("name", "Unknown"))
            if not api_info:
                return company_name, [], None
            try:
                response = await client.get(api_info["url"])
                response.raise_for_status()
                payload = response.json()
                offers = _PARSERS[api_info["type"]](payload, company_name)
                return company_name, offers, None
            except Exception as exc:
                logger.warning("Portal scan failed for %s: %s", company_name, exc)
                return company_name, [], f"{company_name}: {exc}"

        company_results = await asyncio.gather(
            *(fetch_company_jobs(company) for company in companies)
        )

    for _company_name, offers, error in company_results:
        if error:
            errors.append(error)
            continue

        total_jobs_found += len(offers)

        for offer in offers:
            title = offer.get("title", "")
            url = offer.get("url", "")
            if not matcher(title):
                filtered_out += 1
                continue
            if not url or url in seen_urls:
                duplicates += 1
                continue
            seen_urls.add(url)
            new_offers.append(CareerOpsScannedOffer(**offer))

    if new_offers:
        _append_history(new_offers, history_path=history_path)

    return CareerOpsScanData(
        scanned_companies=len(companies),
        total_jobs_found=total_jobs_found,
        filtered_out=filtered_out,
        duplicates=duplicates,
        new_offers=new_offers,
        errors=errors,
    )
