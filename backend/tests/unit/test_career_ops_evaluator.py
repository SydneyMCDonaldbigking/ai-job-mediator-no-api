"""Unit tests for Career Ops job evaluation helpers."""

from app.career_ops.evaluator import (
    DEFAULT_DIMENSION_BLUEPRINT,
    build_job_evaluation_prompt,
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
