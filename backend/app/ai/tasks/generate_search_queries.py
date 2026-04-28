from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from app.ai.core.invoke import invoke_json_task as core_invoke_json_task
from app.ai.parsers.search_queries import (
    SearchQueryTaskResult,
    normalize_search_query_task_result,
)
from app.ai.prompts.search_queries import build_search_query_prompt
from app.schemas.models import ResumeData, SeekSearchPlan

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = object

logger = logging.getLogger(__name__)


class GeneratedSearchQueries(BaseModel):
    candidate_profile_summary: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    location: str = Field(min_length=1)


class GenerateSearchQueriesRunnableInput(BaseModel):
    resume: ResumeData
    language: str = Field(min_length=1)
    default_location: str = Field(min_length=1)
    config: LLMConfig | None = None
    max_tokens: int = 4096
    retries: int = 2


def _resume_text(resume: ResumeData) -> str:
    parts: list[str] = [resume.summary or ""]
    for entry in resume.workExperience:
        parts.append(entry.title)
        parts.extend(entry.description)
    parts.extend(resume.additional.technicalSkills)
    return " ".join(part for part in parts if part).lower()


def _fallback_profile_summary(resume: ResumeData) -> str:
    summary = resume.summary.strip()
    if summary:
        return summary

    for entry in resume.workExperience:
        title = entry.title.strip()
        if title:
            return title

    return "Candidate resume profile"


def _fallback_keywords_en(resume: ResumeData) -> list[str]:
    text = _resume_text(resume)
    keywords: list[str] = []

    if "python" in text and "backend" in text:
        keywords.append("python backend engineer")
    if "platform" in text or "aws" in text:
        keywords.append("platform engineer")
    if "fastapi" in text or "api" in text:
        keywords.append("backend api engineer")

    if not keywords:
        for entry in resume.workExperience:
            title = entry.title.strip().lower()
            if title:
                keywords.append(title)
                break

    if not keywords:
        keywords.append("software engineer")

    normalized_keywords = list(
        dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip())
    )

    safe_fallbacks = [
        "software engineer",
        "backend engineer",
        "platform engineer",
        "python engineer",
        "application engineer",
    ]
    for fallback_keyword in safe_fallbacks:
        if len(normalized_keywords) >= 2:
            break
        if fallback_keyword not in normalized_keywords:
            normalized_keywords.append(fallback_keyword)

    return normalized_keywords[:5]


def _fallback_keywords_ja(resume: ResumeData) -> list[str]:
    text = _resume_text(resume)
    keywords: list[str] = []

    if "backend" in text or "api" in text:
        keywords.append("バックエンドエンジニア")
    if "python" in text:
        keywords.append("python エンジニア")
    if "aws" in text or "platform" in text:
        keywords.append("プラットフォームエンジニア")
    if "fastapi" in text:
        keywords.append("python バックエンドエンジニア")

    if not keywords:
        for entry in resume.workExperience:
            title = entry.title.strip()
            if title:
                keywords.append(title)
                break

    if not keywords:
        keywords.append("ソフトウェアエンジニア")

    normalized_keywords = list(
        dict.fromkeys(keyword.strip() for keyword in keywords if keyword.strip())
    )

    safe_fallbacks = [
        "ソフトウェアエンジニア",
        "バックエンドエンジニア",
        "アプリケーションエンジニア",
        "プラットフォームエンジニア",
        "python エンジニア",
    ]
    for fallback_keyword in safe_fallbacks:
        if len(normalized_keywords) >= 2:
            break
        if fallback_keyword not in normalized_keywords:
            normalized_keywords.append(fallback_keyword)

    return normalized_keywords[:5]


def _fallback_keywords(resume: ResumeData, *, language: str) -> list[str]:
    normalized_language = language.strip().lower()
    if normalized_language == "ja":
        return _fallback_keywords_ja(resume)
    return _fallback_keywords_en(resume)


def _to_generated_search_queries(
    result: SearchQueryTaskResult,
) -> GeneratedSearchQueries:
    return GeneratedSearchQueries(**result.model_dump())


def _build_generate_search_queries_payload(
    task_input: GenerateSearchQueriesRunnableInput,
) -> dict[str, object]:
    prompt = build_search_query_prompt(
        resume=task_input.resume,
        language=task_input.language,
        default_location=task_input.default_location,
    )
    return {
        "prompt": prompt,
        "system_prompt": None,
        "config": task_input.config,
        "max_tokens": task_input.max_tokens,
        "retries": task_input.retries,
    }


async def invoke_json_task(
    prompt: str,
    system_prompt: str | None = None,
    config: LLMConfig | None = None,
    max_tokens: int = 4096,
    retries: int = 2,
) -> dict[str, object]:
    """Compatibility wrapper retained for existing callers and tests."""

    return await core_invoke_json_task(
        prompt,
        system_prompt=system_prompt,
        config=config,
        max_tokens=max_tokens,
        retries=retries,
    )


async def _invoke_generate_search_queries_payload(
    payload: dict[str, object],
) -> dict[str, object]:
    return await invoke_json_task(
        payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        config=payload.get("config"),
        max_tokens=payload.get("max_tokens", 4096),
        retries=payload.get("retries", 2),
    )


def build_generate_search_queries_runnable() -> RunnableSerializable[
    GenerateSearchQueriesRunnableInput, dict[str, object]
]:
    """Build the LangChain runnable pipeline for search query generation."""

    return RunnableLambda(_build_generate_search_queries_payload) | RunnableLambda(
        _invoke_generate_search_queries_payload
    )


async def generate_search_queries(
    *,
    resume: ResumeData,
    language: str,
    default_location: str,
    config: LLMConfig | None = None,
    max_tokens: int = 4096,
    retries: int = 2,
) -> GeneratedSearchQueries:
    task_input = GenerateSearchQueriesRunnableInput(
        resume=resume,
        language=language,
        default_location=default_location,
        config=config,
        max_tokens=max_tokens,
        retries=retries,
    )
    runnable = build_generate_search_queries_runnable()

    try:
        raw_result = await runnable.ainvoke(task_input)
    except Exception:
        logger.exception("Failed to generate search queries with LLM, using fallback")
        return GeneratedSearchQueries(
            candidate_profile_summary=_fallback_profile_summary(resume),
            keywords=_fallback_keywords(resume, language=language),
            location=default_location.strip(),
        )

    parsed_result = SearchQueryTaskResult.model_validate(raw_result)
    normalized_result = normalize_search_query_task_result(parsed_result)
    return _to_generated_search_queries(normalized_result)


def to_seek_search_plan(
    result: GeneratedSearchQueries,
    *,
    resume_id: str,
    source: str = "seek",
) -> SeekSearchPlan:
    return SeekSearchPlan(
        resume_id=resume_id,
        source=source,
        candidate_profile_summary=result.candidate_profile_summary,
        keywords=result.keywords,
        location=result.location,
    )
