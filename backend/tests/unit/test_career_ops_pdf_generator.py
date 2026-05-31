"""Unit tests for Career Ops PDF generation helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.career_ops.pdf_generator import (
    _heuristic_tailor_resume,
    _postprocess_pdf_resume,
    _tailor_resume,
    _render_competencies,
    _render_projects,
    _restore_protected_fields,
    normalize_text_for_ats,
    render_resume_html,
)
from app.schemas.models import ImproveDiffResult, ResumeChange


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


def test_render_competencies_filters_recruiting_noise(sample_resume):
    sample_resume["personalInfo"]["location"] = "Sydney NSW"
    sample_resume["additional"]["technicalSkills"].insert(0, "C")
    sample_resume["additional"]["technicalSkills"].extend(["Figma", "Unreal Engine"])
    html = _render_competencies(
        sample_resume,
        [
            "Python",
            "Agents",
            "Junior Level",
            "People",
            "Project Galileo Search",
            "Sydney",
            "Hybrid",
            "Exclusive opportunity",
            "FastAPI",
            "Docker",
            "Copilot",
        ],
    )

    assert "Python" in html
    assert "FastAPI" in html
    assert "Docker" in html
    assert "Sydney" not in html
    assert "Hybrid" not in html
    assert "Exclusive opportunity" not in html
    assert "Junior Level" not in html
    assert "Project Galileo Search" not in html
    assert "VS Code" not in html
    assert "CLion" not in html
    assert "Copilot" not in html
    assert "Figma" not in html
    assert "Unreal Engine" not in html


def test_render_projects_preserves_bullets(sample_resume):
    html = _render_projects(sample_resume)

    assert '<div class="project-title">OpenAPI Generator' in html
    assert "<ul>" in html
    assert "<li>CLI tool generating API clients from OpenAPI specs</li>" in html
    assert "<li>500+ GitHub stars, used by 30+ companies</li>" in html


def test_render_projects_limits_bullets_to_four(sample_resume):
    sample_resume["personalProjects"][0]["description"] = [
        "Bullet 1",
        "Bullet 2",
        "Bullet 3",
        "Bullet 4",
        "Bullet 5",
    ]

    html = _render_projects(sample_resume)

    assert "<li>Bullet 1</li>" in html
    assert "<li>Bullet 4</li>" in html
    assert "<li>Bullet 5</li>" not in html


def test_render_projects_falls_back_to_project_like_experience(sample_resume):
    sample_resume["personalProjects"] = []
    sample_resume["workExperience"][1]["title"] = "Technical Project Developer"
    sample_resume["workExperience"][1]["company"] = "University Lab"

    html = _render_projects(sample_resume)

    assert "No project data provided" in html


def test_heuristic_tailor_resume_summary_skips_recruiting_noise(sample_resume):
    tailored = _heuristic_tailor_resume(
        sample_resume,
        ["Python", "Sydney", "Full", "time", "Hybrid", "JavaScript"],
    )

    assert "Python" in tailored.summary
    assert "Sydney" not in tailored.summary
    assert "Full" not in tailored.summary
    assert "Hybrid" not in tailored.summary


def test_postprocess_pdf_resume_reorders_more_relevant_experience_first(sample_resume):
    sample_resume["workExperience"].append(
        {
            "id": 3,
            "title": "Technical Project Developer",
            "company": "University Lab",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Built RAG workflow automation in Python.",
                "Ran experiments with LLM evaluation loops.",
            ],
        }
    )

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["Python", "RAG", "workflow automation"],
    )

    assert tailored.workExperience[0].title == "Technical Project Developer"
    assert tailored.workExperience[0].company == "University Lab"


def test_postprocess_pdf_resume_extracts_project_like_experience_into_projects(sample_resume):
    sample_resume["personalProjects"] = []
    sample_resume["workExperience"].append(
        {
            "id": 3,
            "title": "Technical Project Developer",
            "company": "University Lab",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Built RAG workflow automation in Python.",
                "Ran experiments with LLM evaluation loops.",
                "Improved retrieval quality with offline evaluation.",
            ],
        }
    )

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["Python", "RAG", "workflow automation"],
    )

    assert tailored.personalProjects
    assert tailored.personalProjects[0].name == "University Lab"
    assert tailored.personalProjects[0].role == "Technical Project Developer"
    assert "Built RAG workflow automation in Python." in tailored.personalProjects[0].description
    assert any(item.company == "University Lab" for item in tailored.workExperience)


@patch("app.career_ops.pdf_generator.extract_job_keywords_llm", new_callable=AsyncMock)
@patch("app.career_ops.pdf_generator.improve_resume", new_callable=AsyncMock)
async def test_tailor_resume_uses_full_prompt_for_pdf(
    mock_improve_resume,
    mock_extract_keywords,
    sample_resume,
):
    mock_extract_keywords.return_value = {
        "required_skills": ["Python", "RAG"],
        "preferred_skills": [],
        "experience_requirements": [],
        "education_requirements": [],
        "key_responsibilities": [],
        "keywords": ["workflow automation"],
    }
    mock_improve_resume.return_value = {
        "summary": sample_resume["summary"],
        "workExperience": sample_resume["workExperience"],
        "education": sample_resume["education"],
        "personalProjects": sample_resume["personalProjects"],
        "additional": sample_resume["additional"],
        "customSections": sample_resume["customSections"],
        "sectionMeta": sample_resume["sectionMeta"],
    }

    await _tailor_resume(render_resume_html.__globals__["coerce_resume_data"](sample_resume), "Need Python and RAG automation.")

    assert mock_improve_resume.await_args.kwargs["prompt_id"] == "full"


@patch("app.career_ops.pdf_generator.verify_diff_result")
@patch("app.career_ops.pdf_generator.apply_diffs")
@patch("app.career_ops.pdf_generator.generate_resume_diffs", new_callable=AsyncMock)
@patch("app.career_ops.pdf_generator.extract_job_keywords_llm", new_callable=AsyncMock)
@patch("app.career_ops.pdf_generator.improve_resume", new_callable=AsyncMock)
async def test_tailor_resume_uses_diff_fallback_before_heuristic(
    mock_improve_resume,
    mock_extract_keywords,
    mock_generate_diffs,
    mock_apply_diffs,
    mock_verify_diffs,
    sample_resume,
):
    mock_improve_resume.side_effect = ValueError("Failed after 3 attempts")
    mock_extract_keywords.return_value = {
        "required_skills": ["Python", "RAG"],
        "preferred_skills": [],
        "experience_requirements": [],
        "education_requirements": [],
        "key_responsibilities": [],
        "keywords": ["workflow automation"],
    }
    mock_generate_diffs.return_value = ImproveDiffResult(
        changes=[
            ResumeChange(
                path="summary",
                action="replace",
                original=sample_resume["summary"],
                value="Tailored AI summary.",
                reason="More relevant to the JD",
            )
        ],
        strategy_notes="diff fallback",
    )
    improved = dict(sample_resume)
    improved["summary"] = "Tailored AI summary."
    mock_apply_diffs.return_value = (improved, mock_generate_diffs.return_value.changes, [])
    mock_verify_diffs.return_value = []

    tailored, _keywords = await _tailor_resume(
        render_resume_html.__globals__["coerce_resume_data"](sample_resume),
        "Need Python and RAG automation.",
    )

    assert tailored.summary == "Tailored AI summary."
    mock_generate_diffs.assert_awaited_once()
    mock_apply_diffs.assert_called_once()
