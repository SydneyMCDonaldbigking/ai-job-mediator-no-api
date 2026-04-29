from __future__ import annotations

import json
from typing import Any

from app.schemas.models import ResumeData


def _normalize_nested_strings(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_normalize_nested_strings(item) for item in value]
    if isinstance(value, dict):
        return {
            key: _normalize_nested_strings(item)
            for key, item in value.items()
        }
    return value


def normalize_resume_task_result(result: ResumeData) -> ResumeData:
    normalized_data = _normalize_nested_strings(
        result.model_dump(mode="python", exclude_none=False)
    )
    return ResumeData.model_validate(normalized_data)


def parse_resume_json(payload: str) -> ResumeData:
    data = json.loads(payload)
    result = ResumeData.model_validate(data)
    return normalize_resume_task_result(result)
