"""Unit tests for Career Ops job evaluation helpers."""

import asyncio

from app.career_ops import evaluator as evaluator_module
from app.ai.tasks.evaluate_job import GeneratedJobEvaluation
from app.ai.parsers.evaluate_job import EvaluationDimensionResult
from app.career_ops.evaluator import (
    DEFAULT_DIMENSION_BLUEPRINT,
    build_job_evaluation_prompt,
    evaluate_job_fit,
    summarize_af_scores,
)


def test_build_job_evaluation_prompt_mentions_all_af_sections(sample_resume, sample_job_description):
    prompt = build_job_evaluation_prompt(
        resume=sample_resume,
        job_description=sample_job_description,
    )

    for block in ("Block A", "Block B", "Block C", "Block D", "Block E", "Block F"):
        assert block in prompt

    for dimension in DEFAULT_DIMENSION_BLUEPRINT:
        assert dimension["key"] in prompt
        assert dimension["category"] in prompt

    assert "Return valid JSON only" in prompt
    assert "Senior Backend Engineer" in prompt


def test_build_job_evaluation_prompt_requests_compact_json(sample_resume, sample_job_description):
    prompt = build_job_evaluation_prompt(
        resume=sample_resume,
        job_description=sample_job_description,
    )

    assert "Keep the JSON compact" in prompt
    assert "one sentence" in prompt
    assert "at most 2 short evidence bullets" in prompt


def test_summarize_af_scores_groups_dimension_scores():
    dimensions = [
        {"key": "archetype_fit", "category": "A", "score": 4.0},
        {"key": "role_scope", "category": "A", "score": 5.0},
        {"key": "requirements_match", "category": "B", "score": 3.5},
        {"key": "gap_mitigation", "category": "B", "score": 4.5},
        {"key": "seniority_alignment", "category": "C", "score": 3.0},
        {"key": "market_signal", "category": "D", "score": 2.0},
        {"key": "resume_change_plan", "category": "E", "score": 5.0},
        {"key": "interview_story_readiness", "category": "F", "score": 4.0},
    ]

    af_scores = summarize_af_scores(dimensions)

    assert af_scores == {
        "A": 4.5,
        "B": 4.0,
        "C": 3.0,
        "D": 2.0,
        "E": 5.0,
        "F": 4.0,
    }


def test_evaluate_job_fit_rescales_normalized_llm_scores(
    monkeypatch,
    sample_resume,
    sample_job_description,
):
    normalized_scores = {
        "archetype_fit": 0.95,
        "role_scope_clarity": 0.90,
        "hard_requirement_match": 0.97,
        "gap_mitigation_strength": 0.85,
        "seniority_alignment": 0.90,
        "positioning_strategy": 0.88,
        "comp_and_demand_signal": 0.64,
        "resume_customization_leverage": 0.80,
        "linkedin_customization_leverage": 0.75,
        "interview_story_readiness": 0.90,
    }

    async def fake_generate_job_evaluation(**kwargs):
        del kwargs
        return GeneratedJobEvaluation(
            executive_summary="Strong backend fit.",
            archetype="Senior Backend Engineer",
            overall_label="strong fit",
            dimensions=[
                EvaluationDimensionResult(
                    key=dimension["key"],
                    category=dimension["category"],
                    label=dimension["label"],
                    score=normalized_scores[dimension["key"]],
                    rationale="LLM returned normalized scores.",
                    evidence=["Resume/JD overlap"],
                    risks=[],
                )
                for dimension in DEFAULT_DIMENSION_BLUEPRINT
            ],
            tailoring_priorities=["Highlight Kubernetes exposure."],
            interview_focus=["Prepare one platform migration story."],
            keyword_targets=["Python", "FastAPI", "Docker"],
        )

    async def fake_market_signals(*args, **kwargs):
        del args, kwargs
        return None

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
        evaluate_job_fit(
            resume=sample_resume,
            job_description=sample_job_description,
        )
    )

    assert result.overall_score > 4.0
    assert result.dimensions[0].score == 4.75
    assert result.af_scores["D"] == 3.2


def test_evaluate_job_fit_uses_score_derived_label_when_llm_label_conflicts(
    monkeypatch,
    sample_resume,
    sample_job_description,
):
    async def fake_generate_job_evaluation(**kwargs):
        del kwargs
        return GeneratedJobEvaluation(
            executive_summary="Strong backend fit.",
            archetype="Senior Backend Engineer",
            overall_label="strong fit",
            dimensions=[
                EvaluationDimensionResult(
                    key=dimension["key"],
                    category=dimension["category"],
                    label=dimension["label"],
                    score=0.55,
                    rationale="LLM returned normalized scores.",
                    evidence=["Resume/JD overlap"],
                    risks=[],
                )
                for dimension in DEFAULT_DIMENSION_BLUEPRINT
            ],
            tailoring_priorities=["Highlight Kubernetes exposure."],
            interview_focus=["Prepare one platform migration story."],
            keyword_targets=["Python", "FastAPI", "Docker"],
        )

    async def fake_market_signals(*args, **kwargs):
        del args, kwargs
        return None

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
        evaluate_job_fit(
            resume=sample_resume,
            job_description=sample_job_description,
        )
    )

    assert result.overall_score == 2.75
    assert result.overall_label == "stretch"
def test_evaluate_job_fit_removes_stale_no_web_search_claim_when_market_data_exists(
    monkeypatch,
    sample_resume,
    sample_job_description,
):
    async def fake_generate_job_evaluation(**kwargs):
        del kwargs
        raise RuntimeError("LLM unavailable")

    async def fake_market_signals(*args, **kwargs):
        del args, kwargs
        from app.schemas.models import CareerOpsMarketData, CareerOpsMarketSource

        return CareerOpsMarketData(
            role_query="Senior Backend Engineer at TechCorp",
            company_name="TechCorp",
            salary_mentions=["$180,000 - $240,000"],
            demand_summary="Collected 2 live search results for demand and compensation signals.",
            compensation_summary="Salary mentions found: $180,000 - $240,000",
            sources=[
                CareerOpsMarketSource(
                    title="Senior Backend Engineer Salary",
                    url="https://example.com/backend-salary",
                    snippet="Median pay is $180,000 - $240,000.",
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
        evaluate_job_fit(
            resume=sample_resume,
            job_description=sample_job_description,
        )
    )

    comp_dimension = next(
        dimension for dimension in result.dimensions if dimension.key == "comp_and_demand_signal"
    )
    assert "does not run live market web search" not in comp_dimension.rationale
    assert "Salary mentions found: $180,000 - $240,000" in comp_dimension.rationale


def test_evaluate_job_fit_marks_missing_hard_requirements_as_skip(
    monkeypatch,
    sample_resume,
):
    async def fake_generate_job_evaluation(**kwargs):
        del kwargs
        raise RuntimeError("LLM unavailable")

    async def fake_market_signals(*args, **kwargs):
        del args, kwargs
        return None

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
        evaluate_job_fit(
            resume=sample_resume,
            job_description=(
                "Senior Backend Engineer\n\n"
                "Requirements:\n"
                "- 7+ years backend development experience\n"
                "- Ruby on Rails production experience is required\n"
                "- Security clearance is required\n"
            ),
        )
    )

    assert result.priority_label == "skip"
    assert result.tailoring_ready is False
    assert any("ruby on rails" in gap.lower() for gap in result.hard_gaps)
    assert any("security clearance" in gap.lower() for gap in result.hard_gaps)


def test_evaluate_job_fit_exposes_evidence_paths_for_actionable_roles(
    monkeypatch,
    sample_resume,
):
    async def fake_generate_job_evaluation(**kwargs):
        del kwargs
        raise RuntimeError("LLM unavailable")

    async def fake_market_signals(*args, **kwargs):
        del args, kwargs
        return None

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
        evaluate_job_fit(
            resume=sample_resume,
            job_description=(
                "Application Engineer\n\n"
                "Requirements:\n"
                "- Strong Python API development experience\n"
                "- FastAPI or similar framework experience\n"
                "- Experience with Docker and AWS\n"
            ),
        )
    )

    assert result.priority_label in {"high_priority", "worth_checking"}
    assert result.tailoring_ready is True
    assert result.priority_reasons
    assert any(
        match.status in {"strong", "partial"} and match.evidence_paths
        for match in result.evidence_matches
    )


def test_evaluate_job_fit_does_not_treat_unstructured_keywords_as_hard_gaps(
    monkeypatch,
    sample_resume,
):
    async def fake_generate_job_evaluation(**kwargs):
        del kwargs
        raise RuntimeError("LLM unavailable")

    async def fake_market_signals(*args, **kwargs):
        del args, kwargs
        return None

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
        evaluate_job_fit(
            resume=sample_resume,
            job_description=(
                "AI Engineer - Sydney Hybrid. The team builds Python services, "
                "REST APIs, and cloud integrations across AWS, GCP, and Azure. "
                "The role is suitable for someone who can learn client delivery "
                "contexts while applying automation and LLM tooling."
            ),
        )
    )

    assert result.priority_label != "skip"
    assert "GCP" not in result.hard_gaps
    assert "Azure" not in result.hard_gaps
