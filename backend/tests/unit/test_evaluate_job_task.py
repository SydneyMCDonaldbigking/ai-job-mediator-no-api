import asyncio
import importlib

import pytest

from app.ai.parsers.evaluate_job import (
    EvaluationDimensionResult,
    EvaluationTaskResult,
    normalize_evaluation_task_result,
)
from app.ai.tasks.evaluate_job import (
    EvaluateJobRunnableInput,
    GeneratedJobEvaluation,
    build_evaluate_job_runnable,
    generate_job_evaluation,
)
from app.career_ops import evaluator as evaluator_module
from app.schemas.models import CareerOpsMarketData, CareerOpsMarketSource

evaluate_job_module = importlib.import_module("app.ai.tasks.evaluate_job")


def test_normalize_evaluation_task_result_preserves_all_blueprint_keys():
    raw = EvaluationTaskResult(
        executive_summary="Strong backend fit.",
        archetype="Backend platform engineer",
        overall_label="strong fit",
        dimensions=[
            EvaluationDimensionResult(
                key="archetype_fit",
                category="A",
                label="Archetype Fit",
                score=4.2,
                rationale="Clear backend alignment.",
                evidence=["Backend API experience"],
                risks=["Limited domain context"],
            ),
        ],
        tailoring_priorities=["Highlight API scale"],
        interview_focus=["STAR story about platform work"],
        keyword_targets=["Python", "FastAPI"],
    )

    normalized = normalize_evaluation_task_result(raw)

    assert normalized.executive_summary == "Strong backend fit."
    assert normalized.archetype == "Backend platform engineer"
    assert normalized.dimensions[0].key == "archetype_fit"
    assert normalized.keyword_targets == ["Python", "FastAPI"]


def test_generate_job_evaluation_uses_langchain_runnable(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(
            self, task_input: EvaluateJobRunnableInput
        ) -> dict[str, object]:
            assert "Backend Engineer" in task_input.resume_text
            assert "FastAPI" in task_input.job_description
            return {
                "executive_summary": "Strong backend fit.",
                "archetype": "Backend platform engineer",
                "overall_label": "strong fit",
                "dimensions": [
                    {
                        "key": "archetype_fit",
                        "category": "A",
                        "label": "Archetype Fit",
                        "score": 4.2,
                        "rationale": "Clear backend alignment.",
                        "evidence": ["Backend API experience"],
                        "risks": ["Limited domain context"],
                    }
                ],
                "tailoring_priorities": ["Highlight API scale"],
                "interview_focus": ["STAR story about platform work"],
                "keyword_targets": ["Python", "FastAPI"],
            }

    monkeypatch.setattr(
        evaluate_job_module,
        "build_evaluate_job_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_job_evaluation(
            resume_text="Backend Engineer with Python and AWS",
            job_description="Senior FastAPI engineer role",
            keyword_targets=["Python", "FastAPI"],
            market_context="Salary signals available",
        )
    )

    assert isinstance(result, GeneratedJobEvaluation)
    assert result.executive_summary == "Strong backend fit."
    assert result.dimensions[0].key == "archetype_fit"


def test_generate_job_evaluation_surfaces_schema_failures_after_successful_invoke(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(
            self, task_input: EvaluateJobRunnableInput
        ) -> dict[str, object]:
            return {
                "executive_summary": "Strong backend fit.",
                "archetype": "Backend platform engineer",
                "overall_label": "strong fit",
                "dimensions": [],
                "tailoring_priorities": [],
                "interview_focus": [],
                "keyword_targets": [],
            }

    monkeypatch.setattr(
        evaluate_job_module,
        "build_evaluate_job_runnable",
        lambda: FakeRunnable(),
    )

    with pytest.raises(ValueError):
        asyncio.run(
            generate_job_evaluation(
                resume_text="Backend Engineer with Python and AWS",
                job_description="Senior FastAPI engineer role",
                keyword_targets=["Python", "FastAPI"],
                market_context="Salary signals available",
            )
        )


def test_build_evaluate_job_runnable_returns_ainvokable_pipeline():
    runnable = build_evaluate_job_runnable()

    assert hasattr(runnable, "ainvoke")


def test_evaluate_job_fit_delegates_to_ai_task_and_preserves_output_shape(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_generate_job_evaluation(**kwargs):
        assert "FastAPI" in kwargs["job_description"]
        return GeneratedJobEvaluation(
            executive_summary="Strong backend fit.",
            archetype="Backend platform engineer",
            overall_label="strong fit",
            dimensions=[
                EvaluationDimensionResult(
                    key="archetype_fit",
                    category="A",
                    label="Archetype Fit",
                    score=4.2,
                    rationale="Clear backend alignment.",
                    evidence=["Backend API experience"],
                    risks=["Limited domain context"],
                )
            ],
            tailoring_priorities=["Highlight API scale"],
            interview_focus=["STAR story about platform work"],
            keyword_targets=["Python", "FastAPI"],
        )

    async def fake_market_signals(*args, **kwargs):
        return CareerOpsMarketData(
            role_query="Backend Engineer",
            compensation_summary="Salary range seen.",
            demand_summary="Demand looks healthy.",
            salary_mentions=["180k base"],
            sources=[
                CareerOpsMarketSource(
                    title="SEEK salary snapshot",
                    url="https://example.com/seek",
                    snippet="Strong backend demand",
                )
            ],
        )

    monkeypatch.setattr(
        evaluator_module,
        "generate_job_evaluation",
        fake_generate_job_evaluation,
    )
    monkeypatch.setattr(
        evaluator_module,
        "fetch_market_signals",
        fake_market_signals,
    )

    result = asyncio.run(
        evaluator_module.evaluate_job_fit(
            resume={"summary": "Backend engineer with FastAPI and AWS"},
            job_description="Senior FastAPI engineer role",
        )
    )

    assert result.executive_summary == "Strong backend fit."
    assert result.overall_label == "strong fit"
    assert result.dimensions
    assert result.market_data is not None
