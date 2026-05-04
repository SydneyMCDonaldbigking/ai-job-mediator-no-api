import json

from pydantic import BaseModel, Field

MIN_KEYWORDS = 2
MAX_KEYWORDS = 5


class SearchQueryTaskResult(BaseModel):
    candidate_profile_summary: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
    location: str = Field(min_length=1)


def normalize_search_query_task_result(
    result: SearchQueryTaskResult,
) -> SearchQueryTaskResult:
    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in result.keywords:
        normalized = keyword.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)

    normalized_summary = result.candidate_profile_summary.strip()
    normalized_location = result.location.strip()

    if len(deduped) < MIN_KEYWORDS:
        raise ValueError(
            f"keywords must contain between {MIN_KEYWORDS} and {MAX_KEYWORDS} items"
        )
    if len(deduped) > MAX_KEYWORDS:
        raise ValueError(
            f"keywords must contain between {MIN_KEYWORDS} and {MAX_KEYWORDS} items"
        )
    if not normalized_summary:
        raise ValueError("candidate_profile_summary cannot be empty")
    if not normalized_location:
        raise ValueError("location cannot be empty")

    return SearchQueryTaskResult(
        candidate_profile_summary=normalized_summary,
        keywords=deduped,
        location=normalized_location,
    )


def parse_search_query_json(payload: str) -> SearchQueryTaskResult:
    data = json.loads(payload)
    result = SearchQueryTaskResult.model_validate(data)
    return normalize_search_query_task_result(result)
