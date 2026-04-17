"""Unit tests for Career Ops PDF generation helpers."""

from app.career_ops.pdf_generator import (
    _restore_protected_fields,
    normalize_text_for_ats,
    render_resume_html,
)


def test_normalize_text_for_ats_replaces_problematic_unicode():
    normalized, replacements = normalize_text_for_ats(
        'FastAPI — "smart" team…\u00a0with zero-width\u200bchars'
    )

    assert "—" not in normalized
    assert "…" not in normalized
    assert "\u00a0" not in normalized
    assert "\u200b" not in normalized
    assert "-" in normalized
    assert "..." in normalized
    assert replacements["em_dash"] == 1
    assert replacements["ellipsis"] == 1
    assert replacements["nbsp"] == 1
    assert replacements["zero_width"] == 1


def test_render_resume_html_contains_resume_sections(sample_resume):
    html = render_resume_html(
        resume=sample_resume,
        job_description="Need Python, FastAPI, Docker and AWS experience.",
        keywords=["Python", "FastAPI", "Docker", "AWS"],
    )

    assert "<html" in html
    assert "Jane Doe" in html
    assert "Professional Summary" in html
    assert "Core Competencies" in html
    assert "Python" in html
    assert "{{NAME}}" not in html


def test_restore_protected_fields_keeps_personal_info(sample_resume):
    tailored_payload = {
        "personalInfo": {},
        "summary": "Tailored summary",
        "workExperience": sample_resume["workExperience"],
        "education": sample_resume["education"],
        "personalProjects": sample_resume["personalProjects"],
        "additional": sample_resume["additional"],
        "customSections": {},
        "sectionMeta": [],
    }

    restored = _restore_protected_fields(sample_resume, tailored_payload)

    assert restored["personalInfo"]["name"] == "Jane Doe"
    assert restored["personalInfo"]["email"] == "jane@example.com"
