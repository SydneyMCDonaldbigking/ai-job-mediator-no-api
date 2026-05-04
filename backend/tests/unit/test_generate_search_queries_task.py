import asyncio
import importlib
import json

import pytest

from app.ai.parsers.search_queries import (
    SearchQueryTaskResult,
    normalize_search_query_task_result,
    parse_search_query_json,
)
from app.ai.prompts.search_queries import build_search_query_prompt
from app.ai.tasks.generate_search_queries import (
    GeneratedSearchQueries,
    GenerateSearchQueriesRunnableInput,
    generate_search_queries,
)
from app.schemas.models import ResumeData

generate_search_queries_module = importlib.import_module(
    "app.ai.tasks.generate_search_queries"
)


def test_parse_search_query_json_accepts_expected_shape():
    payload = """
    {
      "candidate_profile_summary": "Backend engineer focused on Python APIs",
      "keywords": ["python backend engineer", "platform engineer"],
      "location": "Sydney NSW"
    }
    """

    result = parse_search_query_json(payload)

    assert result.candidate_profile_summary == "Backend engineer focused on Python APIs"
    assert result.keywords == ["python backend engineer", "platform engineer"]
    assert result.location == "Sydney NSW"


def test_normalize_search_query_task_result_dedupes_and_strips():
    raw = SearchQueryTaskResult(
        candidate_profile_summary="  Backend engineer  ",
        keywords=[
            " python backend engineer ",
            "platform engineer",
            "python backend engineer ",
        ],
        location=" Sydney NSW ",
    )

    normalized = normalize_search_query_task_result(raw)

    assert normalized.candidate_profile_summary == "Backend engineer"
    assert normalized.keywords == ["python backend engineer", "platform engineer"]
    assert normalized.location == "Sydney NSW"


def test_parse_search_query_json_rejects_empty_keywords():
    payload = """
    {
      "candidate_profile_summary": "Backend engineer",
      "keywords": [],
      "location": "Sydney NSW"
    }
    """

    try:
        parse_search_query_json(payload)
    except ValueError as exc:
        assert "keywords" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for empty keywords")


def test_parse_search_query_json_rejects_fewer_than_two_keywords():
    payload = """
    {
      "candidate_profile_summary": "Backend engineer",
      "keywords": ["python backend engineer"],
      "location": "Sydney NSW"
    }
    """

    try:
        parse_search_query_json(payload)
    except ValueError as exc:
        assert "keywords" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for fewer than two keywords")


def test_parse_search_query_json_rejects_more_than_five_keywords():
    payload = """
    {
      "candidate_profile_summary": "Backend engineer",
      "keywords": [
        "python backend engineer",
        "platform engineer",
        "api engineer",
        "cloud engineer",
        "software engineer",
        "site reliability engineer"
      ],
      "location": "Sydney NSW"
    }
    """

    try:
        parse_search_query_json(payload)
    except ValueError as exc:
        assert "keywords" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for more than five keywords")


def test_parse_search_query_json_rejects_whitespace_only_candidate_profile_summary():
    payload = """
    {
      "candidate_profile_summary": "   ",
      "keywords": ["python backend engineer", "platform engineer"],
      "location": "Sydney NSW"
    }
    """

    try:
        parse_search_query_json(payload)
    except ValueError as exc:
        assert "candidate_profile_summary" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError for whitespace-only candidate_profile_summary"
        )


def test_parse_search_query_json_rejects_whitespace_only_location():
    payload = """
    {
      "candidate_profile_summary": "Backend engineer",
      "keywords": ["python backend engineer", "platform engineer"],
      "location": "   "
    }
    """

    try:
        parse_search_query_json(payload)
    except ValueError as exc:
        assert "location" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError for whitespace-only location")


def test_build_search_query_prompt_escapes_default_location_in_json_example():
    resume = ResumeData.model_validate({})

    prompt = build_search_query_prompt(
        resume=resume,
        language="English",
        default_location='Sydney "CBD"\nNSW',
    )

    json_block = prompt.split("Return JSON only with this shape:\n", maxsplit=1)[1]
    json_text = json_block.split("\n\nRules:\n", maxsplit=1)[0]

    parsed = json.loads(json_text)

    assert parsed["location"] == 'Sydney "CBD"\nNSW'


def _sample_resume() -> ResumeData:
    return ResumeData.model_validate(
        {
            "summary": "Backend engineer focused on Python APIs",
            "workExperience": [
                {
                    "title": "Backend Engineer",
                    "company": "Example Co",
                    "description": [
                        "Built FastAPI services for internal platforms",
                        "Improved AWS-based deployment workflows",
                    ],
                }
            ],
            "additional": {
                "technicalSkills": ["Python", "FastAPI", "AWS", "Platform Engineering"]
            },
        }
    )


def _sparse_resume() -> ResumeData:
    return ResumeData.model_validate(
        {
            "summary": "",
            "workExperience": [],
            "additional": {"technicalSkills": []},
        }
    )


def test_generate_search_queries_uses_langchain_runnable_and_returns_expected_result(
    monkeypatch: pytest.MonkeyPatch,
):
    resume = _sample_resume()
    calls: dict[str, object] = {}

    class FakeRunnable:
        async def ainvoke(
            self, task_input: GenerateSearchQueriesRunnableInput
        ) -> dict[str, object]:
            calls["task_input"] = task_input
            calls["prompt"] = build_search_query_prompt(
                resume=task_input.resume,
                language=task_input.language,
                default_location=task_input.default_location,
            )
            return {
                "candidate_profile_summary": "Backend engineer focused on Python APIs",
                "keywords": ["python backend engineer", "platform engineer"],
                "location": "Sydney NSW",
            }

    monkeypatch.setattr(
        generate_search_queries_module,
        "build_generate_search_queries_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_search_queries(
            resume=resume,
            language="English",
            default_location="Sydney NSW",
        )
    )

    assert result == GeneratedSearchQueries(
        candidate_profile_summary="Backend engineer focused on Python APIs",
        keywords=["python backend engineer", "platform engineer"],
        location="Sydney NSW",
    )
    assert isinstance(calls["task_input"], GenerateSearchQueriesRunnableInput)
    assert "Backend engineer focused on Python APIs" in str(calls["prompt"])
    assert calls["task_input"].config is None
    assert calls["task_input"].max_tokens == 4096
    assert calls["task_input"].retries == 2


def test_generate_search_queries_falls_back_on_invoke_error(
    monkeypatch: pytest.MonkeyPatch,
):
    resume = _sample_resume()

    class FakeRunnable:
        async def ainvoke(
            self, task_input: GenerateSearchQueriesRunnableInput
        ) -> dict[str, object]:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        generate_search_queries_module,
        "build_generate_search_queries_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_search_queries(
            resume=resume,
            language="English",
            default_location="Sydney NSW",
        )
    )

    assert result == GeneratedSearchQueries(
        candidate_profile_summary="Backend engineer focused on Python APIs",
        keywords=[
            "python backend engineer",
            "platform engineer",
            "backend api engineer",
        ],
        location="Sydney NSW",
    )


def test_generate_search_queries_sparse_resume_fallback_returns_at_least_two_keywords(
    monkeypatch: pytest.MonkeyPatch,
):
    resume = _sparse_resume()

    class FakeRunnable:
        async def ainvoke(
            self, task_input: GenerateSearchQueriesRunnableInput
        ) -> dict[str, object]:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        generate_search_queries_module,
        "build_generate_search_queries_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_search_queries(
            resume=resume,
            language="English",
            default_location="Sydney NSW",
        )
    )

    assert len(result.keywords) >= 2
    assert len(result.keywords) == len(set(result.keywords))
    assert result.location == "Sydney NSW"


def test_generate_search_queries_japanese_fallback_uses_japanese_keywords(
    monkeypatch: pytest.MonkeyPatch,
):
    resume = _sample_resume()

    class FakeRunnable:
        async def ainvoke(
            self, task_input: GenerateSearchQueriesRunnableInput
        ) -> dict[str, object]:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        generate_search_queries_module,
        "build_generate_search_queries_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_search_queries(
            resume=resume,
            language="ja",
            default_location="東京",
        )
    )

    assert result.location == "東京"
    assert len(result.keywords) >= 2
    assert all(keyword.isascii() is False for keyword in result.keywords[:2])
    assert "engineer" not in " ".join(result.keywords).lower()


def test_generate_search_queries_surfaces_schema_failure_after_successful_invoke(
    monkeypatch: pytest.MonkeyPatch,
):
    resume = _sample_resume()

    class FakeRunnable:
        async def ainvoke(
            self, task_input: GenerateSearchQueriesRunnableInput
        ) -> dict[str, object]:
            return {
                "candidate_profile_summary": "Backend engineer focused on Python APIs",
                "keywords": ["python backend engineer"],
                "location": "Sydney NSW",
            }

    monkeypatch.setattr(
        generate_search_queries_module,
        "build_generate_search_queries_runnable",
        lambda: FakeRunnable(),
    )

    with pytest.raises(ValueError):
        asyncio.run(
            generate_search_queries(
                resume=resume,
                language="English",
                default_location="Sydney NSW",
            )
        )
