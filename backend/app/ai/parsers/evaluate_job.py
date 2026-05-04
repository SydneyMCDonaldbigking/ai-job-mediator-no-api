from __future__ import annotations

import json

from pydantic import BaseModel, Field


class EvaluationDimensionResult(BaseModel):
    key: str = Field(min_length=1)
    category: str = Field(min_length=1)
    label: str = Field(min_length=1)
    score: float
    rationale: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class EvaluationTaskResult(BaseModel):
    executive_summary: str = Field(min_length=1)
    archetype: str = Field(min_length=1)
    overall_label: str = Field(min_length=1)
    dimensions: list[EvaluationDimensionResult] = Field(min_length=1)
    tailoring_priorities: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    keyword_targets: list[str] = Field(default_factory=list)


def _clean_string_list(values: list[str]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


def normalize_evaluation_task_result(
    result: EvaluationTaskResult,
) -> EvaluationTaskResult:
    dimensions = [
        EvaluationDimensionResult(
            key=dimension.key.strip(),
            category=dimension.category.strip().upper(),
            label=dimension.label.strip(),
            score=dimension.score,
            rationale=dimension.rationale.strip(),
            evidence=_clean_string_list(dimension.evidence),
            risks=_clean_string_list(dimension.risks),
        )
        for dimension in result.dimensions
    ]
    return EvaluationTaskResult(
        executive_summary=result.executive_summary.strip(),
        archetype=result.archetype.strip(),
        overall_label=result.overall_label.strip(),
        dimensions=dimensions,
        tailoring_priorities=_clean_string_list(result.tailoring_priorities),
        interview_focus=_clean_string_list(result.interview_focus),
        keyword_targets=_clean_string_list(result.keyword_targets),
    )


def parse_evaluation_json(payload: str) -> EvaluationTaskResult:
    parsed = EvaluationTaskResult.model_validate(json.loads(payload))
    return normalize_evaluation_task_result(parsed)
