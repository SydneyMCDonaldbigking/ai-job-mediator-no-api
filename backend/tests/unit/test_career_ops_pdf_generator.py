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


def test_render_competencies_prioritizes_ai_relevant_skills(sample_resume):
    sample_resume["additional"]["technicalSkills"] = [
        "Python",
        "C",
        "SQL",
        "Industrial Automation (OPC Integration)",
        "Computer Automation Scripts",
        "AI Model Fine-Tuning and Deployment",
        "Product User-Centered Design",
        "Data-Driven Decision Making",
        "Prompt Engineering",
        "Model Evaluation",
        "LLM Application Development",
        "RAG Pipeline Design",
    ]

    html = _render_competencies(
        sample_resume,
        [
            "Python",
            "LLM",
            "RAG",
            "workflow automation",
            "data engineering",
            "analytics",
            "prompt engineering",
            "model evaluation",
            "rag pipeline",
        ],
    )
    assert "Python" in html
    assert "AI Model Fine-Tuning and Deployment" in html
    assert "Computer Automation Scripts" in html
    assert "Prompt Engineering" in html
    assert "Model Evaluation" in html
    assert "LLM Application Development" in html
    assert "RAG Pipeline Design" in html
    assert '<span class="competency-tag">C</span>' not in html
    assert "Product User-Centered Design" not in html


def test_render_competencies_can_promote_ai_evidence_from_project_history(sample_resume):
    sample_resume["additional"]["technicalSkills"] = [
        "Python",
        "SQL",
        "Data-Driven Decision Making",
    ]
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "University Lab",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Developed an intelligent WeChat customer service automation system based on RAG.",
                "Implemented NLP sentiment classification and computer vision models for text emotion detection and agricultural pest recognition.",
                "Extended the RAG framework to support full desktop UI automation using OpenClaw.",
            ],
        }
    ]

    html = _render_competencies(
        sample_resume,
        ["Python", "RAG", "workflow automation", "NLP", "computer vision"],
    )

    assert "RAG Workflow Automation" in html
    assert "NLP Sentiment Classification" in html
    assert "Computer Vision Models" in html


def test_render_competencies_prioritizes_ai_evidence_over_generic_tail_items(sample_resume):
    sample_resume["additional"]["technicalSkills"] = [
        "Python",
        "SQL",
        "Data-Driven Decision Making",
        "Industrial Automation (OPC Integration)",
        "Computer Automation Scripts",
    ]
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "University Lab",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Developed an intelligent customer service automation system based on RAG.",
                "Implemented NLP sentiment classification and computer vision models.",
            ],
        }
    ]

    html = _render_competencies(
        sample_resume,
        ["Python", "RAG", "NLP", "computer vision", "workflow automation"],
    )

    assert "RAG Workflow Automation" in html
    assert "NLP Sentiment Classification" in html
    assert "Computer Vision Models" in html


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


def test_postprocess_pdf_resume_enriches_generic_summary_for_ai_profiles(sample_resume):
    sample_resume["summary"] = "Master's student in Information Technology at UNSW."
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "AI & Automation Developer",
            "company": "Factory Collaboration",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Built Python automation for reporting workflows.",
                "Collaborated with consultants and operations stakeholders on AI prototype delivery.",
            ],
        }
    ]
    sample_resume["additional"]["technicalSkills"] = [
        "Python",
        "SQL",
        "Computer Automation Scripts",
        "AI Model Fine-Tuning and Deployment",
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["Python", "AI", "automation", "stakeholders"],
    )

    assert "AI and automation projects" in tailored.summary
    assert "stakeholders and cross-functional teams" in tailored.summary


def test_postprocess_pdf_resume_refines_generic_summary_language(sample_resume):
    sample_resume["summary"] = "Master's student with experience in AI-driven systems, automation scripts, and web-based projects."

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["Python", "AI", "automation"],
    )

    assert "automation tooling" in tailored.summary
    assert "digital product delivery" in tailored.summary


def test_postprocess_pdf_resume_adds_collaboration_clause_when_supported_by_evidence(sample_resume):
    sample_resume["summary"] = "Master's student with experience in AI-driven systems and automation tooling."
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "AI & Automation Developer",
            "company": "Factory Collaboration",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Collaborated with consultants and operations stakeholders on AI prototype delivery.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["AI", "automation", "stakeholders"],
    )

    assert "Collaborates effectively with stakeholders and cross-functional teams" in tailored.summary


def test_postprocess_pdf_resume_reorders_and_tightens_experience_bullets(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Studio Operator",
            "company": "Little Feast Studio",
            "location": "Sydney NSW",
            "years": "2024 - Present",
            "description": [
                "Helped with customer support requests and studio admin.",
                "Worked on stakeholder demos for AI workflow prototypes.",
                "Built Python automation to reduce manual reporting effort by 40%.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["Python", "automation", "AI", "stakeholder"],
    )

    bullets = tailored.workExperience[0].description
    assert bullets[0] == "Built Python automation to reduce manual reporting effort by 40%."
    assert bullets[1] == "Delivered stakeholder demos for AI workflow prototypes."
    assert bullets[2] == "Supported customer support requests and studio admin."


def test_postprocess_pdf_resume_reframes_transferable_studio_bullets(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Studio Operator",
            "company": "Little Feast Studio",
            "location": "Sydney NSW",
            "years": "2024 - Present",
            "description": [
                "Coordinated target customer feedback and helped improve the workflow within the team.",
                "Founded and managed a small social media team focused on content creation and community engagement.",
                "Operated and promoted accounts on Chinese platforms such as Xiaohongshu (RED) and Douyin (TikTok China) achieving consistent audience growth.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["stakeholder", "workflow", "delivery"],
    )

    bullets = tailored.workExperience[0].description
    assert bullets[0] == "Coordinated customer feedback loops and streamlined team workflows to improve content relevance and delivery consistency."
    assert bullets[1] == "Led a social media team delivering content operations and community engagement across multiple channels."
    assert bullets[2] == "Managed and grew social media channels across Xiaohongshu (RED) and Douyin (TikTok China), driving consistent audience growth."


def test_postprocess_pdf_resume_reframes_llm_written_studio_bullets(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Studio Operator",
            "company": "Little Feast Studio",
            "location": "Sydney NSW",
            "years": "2024 - Present",
            "description": [
                "Coordinated target customer feedback and helped improve team workflow, enhancing content relevance and engagement.",
                "Founded and led a social media team focused on content creation and community engagement.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["stakeholder", "workflow", "delivery"],
    )

    bullets = tailored.workExperience[0].description
    assert bullets[0] == "Coordinated customer feedback loops and streamlined team workflows to improve content relevance and delivery consistency."
    assert bullets[1] == "Led a social media team delivering content operations and community engagement across multiple channels."


def test_postprocess_pdf_resume_prioritizes_rag_and_automation_project_bullets(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "University of New South Wales (UNSW)",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Implemented NLP sentiment classification and computer vision models for text emotion detection and agricultural pest recognition.",
                "Extended the RAG framework to support full desktop UI automation using OpenClaw, enabling AI-driven interaction with computer interfaces and workflow automation.",
                "Developed an intelligent WeChat customer service automation system based on Retrieval-Augmented Generation (RAG).",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["AI", "automation", "large language models", "workflow"],
    )

    bullets = tailored.workExperience[0].description
    assert "RAG" in bullets[0] or "Retrieval-Augmented Generation" in bullets[0]
    assert "automation" in bullets[1].lower()


def test_postprocess_pdf_resume_pushes_low_signal_game_bullets_later(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "University of New South Wales (UNSW)",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Extended the RAG framework to support full desktop UI automation using OpenClaw.",
                "Developed the multi-level interactive game Cat vs Dog using Unreal Engine as Lead Technical Developer.",
                "Implemented NLP sentiment classification and computer vision models for text emotion detection and agricultural pest recognition.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["AI", "automation", "computer vision", "workflow"],
    )

    bullets = tailored.workExperience[0].description
    assert "Unreal Engine" not in bullets[0]
    assert "Unreal Engine" not in bullets[1]


def test_postprocess_pdf_resume_prioritizes_model_delivery_before_supporting_pipeline_bullets(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "AI & Automation Developer",
            "company": "Industrial AI Automation Project (Factory Collaboration)",
            "location": "Remote",
            "years": "2025 - Present",
            "description": [
                "Built automation scripts to collect, clean and preprocess equipment data, enabling reliable model inputs.",
                "Applied machine learning techniques to analyse operational parameters, improving prediction accuracy and supporting real-time decision making.",
                "Designed and trained an AI-based prediction model for blast furnace airflow using industrial OPC data to enhance process monitoring.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["AI", "automation", "machine learning", "model"],
    )

    bullets = tailored.workExperience[0].description
    assert bullets[0] == "Designed and trained an AI-based prediction model for blast furnace airflow using industrial OPC data to enhance process monitoring."
    assert bullets[1] == "Applied machine learning techniques to analyse operational parameters, improving prediction accuracy and supporting real-time decision making."


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
