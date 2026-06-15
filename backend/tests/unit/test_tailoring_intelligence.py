"""Unit tests for JD profile and resume evidence mapping."""

from app.career_ops.tailoring_intelligence import (
    JOB_TYPE_AI_ML,
    JOB_TYPE_DATA_ANALYTICS,
    JOB_TYPE_OPERATIONS_CUSTOMER,
    JOB_TYPE_SOFTWARE,
    JOB_TYPE_UX_PRODUCT,
    TAG_AI_ML,
    TAG_COLLABORATION,
    TAG_CUSTOMER,
    TAG_DATA,
    TAG_DESIGN,
    TAG_LOW_RELEVANCE,
    TAG_SOFTWARE,
    TAG_TECHNICAL,
    build_resume_evidence_map,
    classify_resume_entry,
    infer_job_profile,
)


def test_infer_job_profile_detects_core_role_types():
    assert infer_job_profile(
        "Build LLM agents, RAG workflows, model evaluation and machine learning pipelines."
    ).primary_type == JOB_TYPE_AI_ML
    assert infer_job_profile(
        "Junior Software Engineer building Python APIs, React screens, SQL queries, Git tests and deployments."
    ).primary_type == JOB_TYPE_SOFTWARE
    assert infer_job_profile(
        "UX Product Designer owning user-centred design, prototyping, Figma and stakeholder workshops."
    ).primary_type == JOB_TYPE_UX_PRODUCT
    assert infer_job_profile(
        "Data analyst role using SQL, dashboards, analytics, experiments and business insights."
    ).primary_type == JOB_TYPE_DATA_ANALYTICS
    assert infer_job_profile(
        "Customer operations role improving service workflows, customer feedback, rostering and team coordination."
    ).primary_type == JOB_TYPE_OPERATIONS_CUSTOMER


def test_infer_job_profile_prefers_ai_when_ai_and_software_scores_tie():
    profile = infer_job_profile(
        "AI Engineer building Python and JavaScript workflow automation for business teams.",
        ["AI Engineer", "Python", "JavaScript", "workflow automation"],
    )

    assert profile.primary_type == JOB_TYPE_AI_ML


def test_infer_job_profile_handles_software_role_and_plural_apis():
    profile = infer_job_profile(
        "Junior software role requiring REST APIs and documentation.",
        ["REST APIs"],
    )

    assert profile.primary_type == JOB_TYPE_SOFTWARE


def test_build_resume_evidence_map_tags_entries_against_ai_jd(sample_resume):
    sample_resume["workExperience"] = [
        {
            "id": 1,
            "title": "Machine Learning Intern",
            "company": "RetailOps Analytics",
            "location": "Sydney",
            "years": "2025",
            "description": [
                "Built Python data pipelines and trained a churn prediction model.",
                "Collaborated with analysts to evaluate model outputs.",
            ],
        },
        {
            "id": 2,
            "title": "Cafe Supervisor",
            "company": "Northside Cafe",
            "location": "Sydney",
            "years": "2023",
            "description": [
                "Coordinated customer feedback loops and trained new staff.",
            ],
        },
        {
            "id": 3,
            "title": "Founder & Operator",
            "company": "Independent Retail Brand",
            "location": "",
            "years": "",
            "description": [
                "Designed original products and identified consumer trends.",
            ],
        },
    ]
    sample_resume["personalProjects"] = [
        {
            "id": 1,
            "name": "RAG Support Assistant",
            "role": "Developer",
            "years": "2025",
            "description": [
                "Developed a RAG assistant using vector retrieval and LLM APIs.",
                "Implemented answer quality evaluation scripts.",
            ],
        }
    ]
    profile = infer_job_profile(
        "AI Engineer building LLM applications, RAG workflows, Python services and model evaluation.",
        ["AI Engineer", "LLM", "RAG", "Python", "model evaluation"],
    )

    evidence_map = build_resume_evidence_map(
        sample_resume,
        keyword_targets=["AI Engineer", "LLM", "RAG", "Python", "model evaluation"],
        job_profile=profile,
    )

    ml_entry = evidence_map.find("workExperience", 0)
    cafe_entry = evidence_map.find("workExperience", 1)
    retail_entry = evidence_map.find("workExperience", 2)
    project_entry = evidence_map.find("personalProjects", 0)

    assert {TAG_AI_ML, TAG_DATA, TAG_TECHNICAL, TAG_COLLABORATION}.issubset(set(ml_entry.tags))
    assert {TAG_CUSTOMER, TAG_COLLABORATION}.issubset(set(cafe_entry.tags))
    assert TAG_LOW_RELEVANCE in retail_entry.tags
    assert project_entry.relevance_score > cafe_entry.relevance_score
    assert {TAG_AI_ML, TAG_TECHNICAL}.issubset(set(project_entry.tags))


def test_classify_resume_entry_keeps_retail_evidence_for_retail_jd():
    profile = infer_job_profile(
        "Retail brand coordinator role focused on consumer trends, product planning and customer insights.",
        ["retail brand", "consumer trends", "product planning", "customer insights"],
    )
    entry = classify_resume_entry(
        section="workExperience",
        index=0,
        title="Founder & Operator",
        organization="Independent Retail Brand",
        descriptions=[
            "Designed original products and identified consumer trends.",
        ],
        keyword_targets=["retail brand", "consumer trends", "product planning", "customer insights"],
        job_profile=profile,
    )

    assert TAG_LOW_RELEVANCE not in entry.tags
    assert {TAG_CUSTOMER, TAG_DESIGN}.issubset(set(entry.tags))
    assert entry.relevance_score > 0
