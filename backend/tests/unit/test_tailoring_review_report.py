"""Unit tests for JD-specific resume tailoring review reports."""

import copy

from app.career_ops.tailoring_review import build_tailoring_review_report
from app.schemas.models import ResumeData, TailoredPDFResult


def test_review_report_maps_supported_and_unsupported_keywords(sample_resume):
    tailored_resume = copy.deepcopy(sample_resume)
    tailored_resume["workExperience"][0]["description"] = [
        "Designed and built REST APIs serving 50K requests/day using Python, FastAPI, and Docker.",
        "Mentored 3 junior developers on backend best practices.",
    ]

    report = build_tailoring_review_report(
        original_resume=sample_resume,
        tailored_resume=tailored_resume,
        job_description="Need Python, FastAPI, Docker, Kubernetes and stakeholder collaboration.",
        keyword_targets=["Python", "FastAPI", "Docker", "Kubernetes", "stakeholder collaboration"],
    )

    python_evidence = next(item for item in report.keyword_evidence if item.keyword == "Python")
    kubernetes_evidence = next(item for item in report.keyword_evidence if item.keyword == "Kubernetes")

    assert python_evidence.supported is True
    assert "workExperience[0].description[0]" in python_evidence.evidence_paths
    assert kubernetes_evidence.supported is False
    assert kubernetes_evidence.evidence_paths == []
    assert "Kubernetes" in report.unsupported_keywords


def test_review_report_keeps_low_relevance_entries_as_lower_priority(sample_resume):
    tailored_resume = copy.deepcopy(sample_resume)
    tailored_resume["workExperience"].append(
        {
            "id": 3,
            "title": "Retail Assistant",
            "company": "Corner Store",
            "location": "Sydney",
            "years": "2022",
            "description": ["Handled checkout operations."],
        }
    )

    report = build_tailoring_review_report(
        original_resume=sample_resume,
        tailored_resume=tailored_resume,
        job_description="Junior software engineer role requiring Python, REST APIs, SQL, Git and testing.",
        keyword_targets=["Python", "REST APIs", "SQL", "Git", "testing"],
    )

    retail_entry = next(
        entry for entry in report.entry_reviews if entry.title == "Retail Assistant"
    )

    assert retail_entry.decision == "kept_lower_priority"
    assert "low_relevance" in retail_entry.evidence_tags
    assert report.preservation_summary.work_experience_original_count == 2
    assert report.preservation_summary.work_experience_tailored_count == 3
    assert report.preservation_summary.removed_work_experience_count == 0


def test_review_report_changes_with_jd_type(sample_resume):
    software_report = build_tailoring_review_report(
        original_resume=sample_resume,
        tailored_resume=sample_resume,
        job_description="Software engineer building Python FastAPI services, Docker deployments and REST APIs.",
        keyword_targets=["Python", "FastAPI", "Docker", "REST APIs"],
    )
    ux_report = build_tailoring_review_report(
        original_resume=sample_resume,
        tailored_resume=sample_resume,
        job_description="UX product role focused on Figma, user-centred design and stakeholder workshops.",
        keyword_targets=["Figma", "user-centred design", "stakeholder workshops"],
    )

    assert software_report.job_profile.primary_type == "software_engineering"
    assert ux_report.job_profile.primary_type == "ux_product"
    assert software_report.scores.ats_score > ux_report.scores.ats_score
    assert software_report.top_alignment_reasons != ux_report.top_alignment_reasons


def test_review_report_filters_recruiting_noise_from_keyword_display(sample_resume):
    report = build_tailoring_review_report(
        original_resume=sample_resume,
        tailored_resume=sample_resume,
        job_description="Junior software role in Sydney requiring Python and Kubernetes exposure.",
        keyword_targets=["Python", "Kubernetes", "Junior", "Sydney", "requiring", "exposure"],
    )

    visible_keywords = [item.keyword for item in report.keyword_evidence]

    assert "Python" in visible_keywords
    assert "Kubernetes" in visible_keywords
    assert "Junior" not in visible_keywords
    assert "Sydney" not in visible_keywords
    assert "requiring" not in visible_keywords
    assert "exposure" not in visible_keywords
    assert "Kubernetes" in report.unsupported_keywords


def test_tailored_pdf_result_can_carry_review_report(sample_resume):
    report = build_tailoring_review_report(
        original_resume=sample_resume,
        tailored_resume=sample_resume,
        job_description="Need Python and FastAPI.",
        keyword_targets=["Python", "FastAPI"],
    )

    result = TailoredPDFResult(
        filename="jane-doe-tailored.pdf",
        pdf_bytes=b"%PDF-1.4",
        tailored_resume=ResumeData.model_validate(sample_resume),
        keyword_targets=["Python", "FastAPI"],
        review_report=report,
    )

    assert result.review_report is not None
    assert result.review_report.keyword_evidence[0].keyword == "Python"
