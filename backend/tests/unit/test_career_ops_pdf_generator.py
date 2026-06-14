"""Unit tests for Career Ops PDF generation helpers."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.career_ops.pdf_generator import (
    _TEMPLATE_FILES,
    _heuristic_tailor_resume,
    _postprocess_pdf_resume,
    _select_competencies,
    _select_resume_template,
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


def test_render_resume_html_can_force_resume_template(sample_resume):
    html = render_resume_html(
        resume=sample_resume,
        job_description="Need Python, FastAPI, Docker and AWS experience.",
        keywords=["Python", "FastAPI", "Docker", "AWS"],
        template_name="compact",
    )

    assert 'data-template="compact"' in html
    assert "grid-template-columns: 34% 1fr" in html
    assert "Jane Doe" in html
    assert "{{TEMPLATE_NAME}}" not in html


def test_select_resume_template_uses_env_override(monkeypatch):
    monkeypatch.setenv("RESUME_TEMPLATE", "executive")

    selected_template, template_path = _select_resume_template()

    assert selected_template == "executive"
    assert template_path == _TEMPLATE_FILES["executive"]


@patch("app.career_ops.resume_renderer.random.choice")
def test_select_resume_template_randomizes_by_default(mock_choice, monkeypatch):
    monkeypatch.delenv("RESUME_TEMPLATE", raising=False)
    mock_choice.return_value = "modern"

    selected_template, template_path = _select_resume_template()

    mock_choice.assert_called_once()
    assert selected_template == "modern"
    assert template_path == _TEMPLATE_FILES["modern"]


def test_pdf_generator_keeps_candidate_content_out_of_source_code():
    import app.career_ops.pdf_generator as pdf_generator

    source = pdf_generator.Path(pdf_generator.__file__).read_text(encoding="utf-8")

    assert "TIANQI" not in source
    assert "Little Feast" not in source
    assert "Cat vs Dog" not in source


def test_all_resume_templates_render_without_leftover_placeholders(sample_resume):
    for template_name in _TEMPLATE_FILES:
        html = render_resume_html(
            resume=sample_resume,
            job_description="Need Python, FastAPI, Docker and AWS experience.",
            keywords=["Python", "FastAPI", "Docker", "AWS"],
            template_name=template_name,
        )

        assert f'data-template="{template_name}"' in html
        assert "{{" not in html
        assert "Jane Doe" in html
        assert "Professional Summary" in html


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


def test_render_resume_html_preserves_full_skills_section(sample_resume):
    sample_resume["additional"]["technicalSkills"] = [
        "Python",
        "C",
        "CLion",
        "Figma",
        "Unreal Engine",
        "VS Code",
        "Industrial Automation (OPC Integration)",
        "AI Model Fine-Tuning and Deployment",
    ]

    html = render_resume_html(
        sample_resume,
        job_description="Need Python, RAG, workflow automation and industrial AI.",
        keywords=["Python", "RAG", "workflow automation", "industrial AI"],
    )

    assert '<span class="skill-category">Technical:</span>' in html
    assert "Python" in html
    assert "Industrial Automation (OPC Integration)" in html
    assert "AI Model Fine-Tuning and Deployment" in html
    assert '<span class="competency-tag">C</span>' not in html
    assert '<span class="competency-tag">Figma</span>' not in html
    assert "CLion" in html
    assert "Figma" in html
    assert "Unreal Engine" in html
    assert "VS Code" in html


def test_render_resume_html_hides_certifications_section_when_empty(sample_resume):
    sample_resume["additional"]["certificationsTraining"] = []

    html = render_resume_html(
        sample_resume,
        job_description="Need Python and AI workflow automation.",
        keywords=["Python", "AI", "workflow automation"],
    )

    assert "Certifications" not in html
    assert "No certifications provided" not in html


def test_render_projects_preserves_bullets(sample_resume):
    html = _render_projects(sample_resume)

    assert '<div class="project-title">OpenAPI Generator' in html
    assert "<ul>" in html
    assert "<li>CLI tool generating API clients from OpenAPI specs</li>" in html
    assert "<li>500+ GitHub stars, used by 30+ companies</li>" in html


def test_render_projects_preserves_all_bullets(sample_resume):
    sample_resume["personalProjects"][0]["description"] = [
        "Bullet 1",
        "Bullet 2",
        "Bullet 3",
        "Bullet 4",
        "Bullet 5",
        "Bullet 6",
    ]

    html = _render_projects(sample_resume)

    assert "<li>Bullet 1</li>" in html
    assert "<li>Bullet 4</li>" in html
    assert "<li>Bullet 5</li>" in html
    assert "<li>Bullet 6</li>" in html


def test_render_experience_preserves_all_bullets(sample_resume):
    sample_resume["workExperience"][0]["description"] = [
        "Bullet 1",
        "Bullet 2",
        "Bullet 3",
        "Bullet 4",
        "Bullet 5",
    ]

    html = render_resume_html(
        sample_resume,
        job_description="Need Python and FastAPI.",
        keywords=["Python", "FastAPI"],
    )

    assert "<li>Bullet 1</li>" in html
    assert "<li>Bullet 4</li>" in html
    assert "<li>Bullet 5</li>" in html


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
            "title": "AI & Automation Developer",
            "company": "Industrial AI Automation Project (Factory Collaboration)",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Designed and trained an AI-based prediction model in Python.",
                "Built workflow automation for industrial data pipelines.",
            ],
        }
    )

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["Python", "RAG", "workflow automation"],
    )

    assert tailored.workExperience[0].title == "AI & Automation Developer"
    assert tailored.workExperience[0].company == "Industrial AI Automation Project (Factory Collaboration)"


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
    assert all(item.company != "University Lab" for item in tailored.workExperience)


def test_postprocess_pdf_resume_moves_unsw_project_out_of_work_experience(sample_resume):
    sample_resume["personalProjects"] = []
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "University of New South Wales (UNSW)",
            "location": "Sydney NSW, Australia",
            "years": "2025 - Present",
            "description": [
                "Developed an intelligent WeChat customer service automation system based on RAG.",
                "Extended the RAG framework to support full desktop UI automation using OpenClaw.",
            ],
        },
        {
            "id": 2,
            "title": "AI & Automation Developer",
            "company": "Industrial AI Automation Project (Factory Collaboration)",
            "location": "Remote",
            "years": "Dec 2025 - Feb 2026",
            "description": [
                "Designed and trained an AI-based prediction model for blast furnace airflow.",
            ],
        },
        {
            "id": 3,
            "title": "Studio Operator",
            "company": "Little Feast Studio",
            "location": "Chengdu, China",
            "years": "Aug 2018 - Aug 2024",
            "description": ["Coordinated target customer feedback and helped improve team workflow."],
        },
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["RAG", "AI", "automation", "workflow"],
    )

    assert all(item.company != "University of New South Wales (UNSW)" for item in tailored.workExperience)
    assert any(item.company == "Industrial AI Automation Project (Factory Collaboration)" for item in tailored.workExperience)
    assert any(project.name == "University of New South Wales (UNSW)" for project in tailored.personalProjects)
    assert all(project.name != "Industrial AI Automation Project (Factory Collaboration)" for project in tailored.personalProjects)


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


def test_postprocess_pdf_resume_uses_generic_workflow_wording_for_non_content_roles(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Cafe Supervisor",
            "company": "Northside Cafe",
            "location": "Melbourne VIC",
            "years": "2021 - 2024",
            "description": [
                "Coordinated customer feedback and helped improve team workflow.",
                "Managed rosters and trained junior staff.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["stakeholder", "workflow", "operations"],
    )

    bullets = tailored.workExperience[0].description
    assert bullets[0] == "Coordinated customer feedback loops and streamlined team workflows to improve operational consistency."
    assert "content relevance" not in bullets[0]


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

    unsw_project = next(project for project in tailored.personalProjects if project.name == "University of New South Wales (UNSW)")
    bullets = unsw_project.description
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
                "Designed and prototyped legal consultation platform user flows for online legal assistance services.",
                "Conducted exploratory data analysis on Airbnb datasets to uncover pricing dynamics.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["AI", "automation", "computer vision", "workflow"],
    )

    unsw_project = next(project for project in tailored.personalProjects if project.name == "University of New South Wales (UNSW)")
    bullets = unsw_project.description
    assert "Unreal Engine" not in bullets[0]
    assert "Unreal Engine" not in bullets[1]
    assert all("Unreal Engine" not in bullet for bullet in bullets[:4])


def test_postprocess_pdf_resume_keeps_five_strong_project_bullets(sample_resume):
    sample_resume["personalProjects"] = []
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "University of New South Wales (UNSW)",
            "location": "Sydney NSW",
            "years": "2025 - Present",
            "description": [
                "Developed an intelligent WeChat customer service automation system based on RAG.",
                "Extended the RAG framework to support full desktop UI automation using OpenClaw.",
                "Implemented NLP sentiment classification and computer vision models for text emotion detection and agricultural pest recognition.",
                "Designed and prototyped legal consultation platform user flows for online legal assistance services.",
                "Conducted exploratory data analysis on Airbnb datasets to uncover pricing dynamics and booking patterns.",
                "Developed the multi-level interactive game Cat vs Dog using Unreal Engine.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["RAG", "workflow automation", "NLP", "computer vision", "data analysis"],
    )

    project = next(project for project in tailored.personalProjects if project.name == "University of New South Wales (UNSW)")
    assert len(project.description) == 6
    assert any("exploratory data analysis" in bullet for bullet in project.description)
    assert any("Unreal Engine" in bullet for bullet in project.description)


def test_postprocess_pdf_resume_keeps_low_signal_project_bullets_after_stronger_evidence(sample_resume):
    sample_resume["personalProjects"] = []
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "Monash University AI Lab",
            "location": "Melbourne VIC",
            "years": "2024",
            "description": [
                "Developed a RAG assistant for student services using vector retrieval and LLM APIs.",
                "Implemented model evaluation scripts for answer quality and hallucination checks.",
                "Built a small Unity game prototype for a class demo.",
                "Designed Figma screens for the project presentation.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["RAG", "LLM", "model evaluation", "workflow automation"],
    )

    project = next(project for project in tailored.personalProjects if project.name == "Monash University AI Lab")
    assert any("RAG assistant" in bullet for bullet in project.description)
    assert any("model evaluation" in bullet for bullet in project.description)
    assert any("Unity" in bullet for bullet in project.description)
    assert any("Figma" in bullet for bullet in project.description)
    assert all("Unity" not in bullet and "Figma" not in bullet for bullet in project.description[:2])


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


def test_postprocess_pdf_resume_professionalizes_internship_bullets(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Software Engineering Intern",
            "company": "Campus Services Platform",
            "location": "Sydney NSW",
            "years": "2025",
            "description": [
                "worked on a Python API for student bookings.",
                "helped debug SQL problems and fixed some bugs.",
                "made docs for deployment.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["Python", "API", "SQL", "debugging", "deployment"],
    )

    bullets = tailored.workExperience[0].description
    assert "Worked on" not in " ".join(bullets)
    assert "helped debug" not in " ".join(bullets).casefold()
    assert "made docs" not in " ".join(bullets).casefold()
    assert "Contributed to development of a Python API for student bookings." in bullets
    assert "Supported debugging of SQL issues and resolved defects." in bullets
    assert "Prepared deployment documentation." in bullets


def test_postprocess_pdf_resume_professionalizes_academic_project_bullets(sample_resume):
    sample_resume["personalProjects"] = []
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "University AI Lab",
            "location": "Sydney NSW",
            "years": "2025",
            "description": [
                "made a RAG chatbot for student questions.",
                "used Python scripts to check answers.",
                "worked with 3 teammates to test it with users.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["RAG", "Python", "model evaluation", "user testing", "collaboration"],
    )

    project = next(project for project in tailored.personalProjects if project.name == "University AI Lab")
    assert "Developed a RAG chatbot for student questions." in project.description
    assert "Implemented Python scripts to evaluate answer quality." in project.description
    assert "Collaborated with 3 teammates to test the solution with users." in project.description


def test_postprocess_pdf_resume_keeps_low_relevance_role_but_sorts_it_lower(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "AI & Automation Developer",
            "company": "Industrial AI Automation Project",
            "location": "Remote",
            "years": "2025",
            "description": [
                "Developed an AI-based prediction model using industrial OPC data.",
                "Built Python automation scripts for model training workflows.",
            ],
        },
        {
            "id": 2,
            "title": "Founder & Operator",
            "company": "Independent Retail Brand",
            "location": "",
            "years": "",
            "description": [
                "Founded and operated an independent retail brand, designing original products and identifying consumer trends.",
            ],
        },
        {
            "id": 3,
            "title": "Studio Operator",
            "company": "Little Feast Studio",
            "location": "Chengdu",
            "years": "2018 - 2024",
            "description": [
                "Coordinated customer feedback loops and improved team workflows.",
                "Led social media content operations across multiple channels.",
            ],
        },
    ]
    sample_resume["personalProjects"] = [
        {
            "id": 1,
            "name": "RAG Customer Service Automation",
            "role": "Developer",
            "years": "2025",
            "description": [
                "Developed a RAG customer service automation system.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["AI Engineer", "LLM", "workflow automation", "Python"],
    )

    assert any(item.company == "Independent Retail Brand" for item in tailored.workExperience)
    assert tailored.workExperience[-1].company == "Independent Retail Brand"
    assert any(item.company == "Little Feast Studio" for item in tailored.workExperience)


def test_postprocess_pdf_resume_uses_evidence_map_for_role_type_sorting(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Machine Learning Intern",
            "company": "RetailOps Analytics",
            "location": "Sydney",
            "years": "2025",
            "description": [
                "Built a churn prediction model and evaluated model outputs.",
            ],
        },
        {
            "id": 2,
            "title": "Junior Software Developer",
            "company": "Campus Services Platform",
            "location": "Sydney",
            "years": "2024",
            "description": [
                "Implemented React components and REST API integrations.",
                "Debugged SQL queries, maintained Git branches and wrote unit tests.",
            ],
        },
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["Software Engineer", "React", "REST API", "SQL", "Git", "unit tests"],
    )

    assert tailored.workExperience[0].title == "Junior Software Developer"


def test_postprocess_pdf_resume_keeps_role_when_it_matches_non_technical_jd(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Founder & Operator",
            "company": "Independent Retail Brand",
            "location": "",
            "years": "",
            "description": [
                "Founded and operated an independent retail brand, designing original products and identifying consumer trends.",
            ],
        },
        {
            "id": 2,
            "title": "Content Studio Operator",
            "company": "Little Feast Studio",
            "location": "Chengdu",
            "years": "2018 - 2024",
            "description": [
                "Managed social media content operations and audience feedback loops.",
            ],
        },
        {
            "id": 3,
            "title": "Customer Service Assistant",
            "company": "Local Cafe",
            "location": "Sydney",
            "years": "2023",
            "description": [
                "Handled customer enquiries and supported daily operations.",
            ],
        },
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["retail brand", "consumer trends", "social media", "customer insights"],
    )

    assert any(item.company == "Independent Retail Brand" for item in tailored.workExperience)


def test_postprocess_pdf_resume_does_not_force_ai_summary_for_non_ai_jd(sample_resume):
    sample_resume["summary"] = (
        "Graduate IT student with experience in user-centred design, workflow mapping, "
        "and stakeholder communication."
    )
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Machine Learning Intern",
            "company": "RetailOps Analytics",
            "location": "Sydney NSW",
            "years": "2025",
            "description": [
                "Developed a churn prediction model in scikit-learn and presented model trade-offs to product stakeholders.",
            ],
        }
    ]

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["user-centred design", "workflow mapping", "prototyping"],
    )

    assert "Brings hands-on experience delivering AI" not in tailored.summary


def test_select_competencies_prioritizes_ux_skills_over_ai_evidence_for_ux_jd(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Technical Project Developer",
            "company": "University AI Lab",
            "location": "Sydney NSW",
            "years": "2025",
            "description": [
                "Developed a RAG assistant using vector retrieval and LLM APIs.",
                "Implemented model evaluation scripts for answer quality checks.",
                "Worked with designers to translate Figma prototypes into responsive user flows.",
            ],
        }
    ]
    sample_resume["additional"]["technicalSkills"] = [
        "Python",
        "RAG",
        "LLM APIs",
        "User-Centred Design",
        "Stakeholder Communication",
        "Prototyping",
        "Product Thinking",
        "Figma",
        "React",
        "SQL",
    ]

    competencies = _select_competencies(
        sample_resume,
        ["user-centred design", "stakeholder communication", "prototyping", "product thinking", "Figma"],
        limit=8,
    )

    assert competencies[:5] == [
        "User-Centred Design",
        "Stakeholder Communication",
        "Prototyping",
        "Product Thinking",
        "Figma",
    ]
    assert "RAG Workflow Automation" not in competencies[:6]
    assert "LLM Solution Prototyping" not in competencies[:6]


def test_postprocess_pdf_resume_limits_summary_to_three_sentences(sample_resume):
    sample_resume["summary"] = (
        "Graduate IT student with user-centred design experience. "
        "Skilled in stakeholder communication and prototyping. "
        "Works with engineers to improve workflows. "
        "Also has broad AI automation experience. "
        "Enjoys learning new tools quickly."
    )

    tailored = _postprocess_pdf_resume(
        sample_resume,
        ["user-centred design", "stakeholder communication", "prototyping"],
    )

    assert tailored.summary.count(".") <= 3
    assert "Also has broad AI automation experience" not in tailored.summary


@patch("app.career_ops.resume_tailoring.extract_job_keywords_llm", new_callable=AsyncMock)
@patch("app.career_ops.resume_tailoring.improve_resume", new_callable=AsyncMock)
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


@patch("app.career_ops.resume_tailoring.extract_job_keywords_llm", new_callable=AsyncMock)
@patch("app.career_ops.resume_tailoring.improve_resume", new_callable=AsyncMock)
async def test_tailor_resume_uses_structured_job_keywords_for_pdf_targets(
    mock_improve_resume,
    mock_extract_keywords,
    sample_resume,
):
    mock_extract_keywords.return_value = {
        "required_skills": ["User-Centred Design", "Prototyping"],
        "preferred_skills": ["Stakeholder Communication"],
        "experience_requirements": [],
        "education_requirements": [],
        "key_responsibilities": ["workflow mapping", "usability feedback"],
        "keywords": ["Product Thinking", "Collaboration"],
    }
    mock_improve_resume.return_value = {
        "summary": sample_resume["summary"],
        "workExperience": sample_resume["workExperience"],
        "education": sample_resume["education"],
        "personalProjects": sample_resume["personalProjects"],
        "additional": {
            **sample_resume["additional"],
            "technicalSkills": [
                "Python",
                "RAG",
                "User-Centred Design",
                "Prototyping",
                "Stakeholder Communication",
            ],
        },
        "customSections": sample_resume["customSections"],
        "sectionMeta": sample_resume["sectionMeta"],
    }

    _tailored, keyword_targets = await _tailor_resume(
        render_resume_html.__globals__["coerce_resume_data"](sample_resume),
        "SEEK UX Designer. Design real-world workflows used daily and own UX.",
    )

    assert keyword_targets[:3] == [
        "User-Centred Design",
        "Prototyping",
        "Stakeholder Communication",
    ]


@patch("app.career_ops.resume_tailoring.verify_diff_result")
@patch("app.career_ops.resume_tailoring.apply_diffs")
@patch("app.career_ops.resume_tailoring.generate_resume_diffs", new_callable=AsyncMock)
@patch("app.career_ops.resume_tailoring.extract_job_keywords_llm", new_callable=AsyncMock)
@patch("app.career_ops.resume_tailoring.improve_resume", new_callable=AsyncMock)
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
