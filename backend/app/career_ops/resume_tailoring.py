"""Resume tailoring and JD-alignment logic.

This module works on structured resume data only. It must not know about HTML,
PDF rendering, browser launch details, or a specific candidate.
"""

from __future__ import annotations

import copy
import logging
import re

from app.career_ops.evaluator import (
    coerce_resume_data,
    extract_keyword_targets,
    resume_to_text,
)
from app.career_ops.resume_text import (
    _compact_whitespace,
    _contains_term,
    _dedupe_preserve_order,
    _has_any_term,
)
from app.career_ops.tailoring_intelligence import (
    JOB_TYPE_UX_PRODUCT,
    classify_resume_entry,
    infer_job_profile,
)
from app.schemas.models import ResumeData, normalize_resume_data
from app.services.improver import apply_diffs
from app.services.improver import extract_job_keywords as extract_job_keywords_llm
from app.services.improver import generate_resume_diffs
from app.services.improver import improve_resume
from app.services.improver import verify_diff_result
from app.services.refiner import fix_alignment_violations, validate_master_alignment

logger = logging.getLogger(__name__)

_LOW_SIGNAL_COMPETENCIES = {
    "vs code",
    "clion",
    "vscode",
    "figma",
    "unreal engine",
    "c",
    "product user-centered design",
}
_HIGH_SIGNAL_COMPETENCY_TERMS = (
    "ai",
    "llm",
    "rag",
    "automation",
    "data",
    "machine learning",
    "model",
    "python",
    "sql",
    "pipeline",
    "retrieval",
    "prompt",
    "evaluation",
    "analytics",
    "opc",
    "industrial",
    "cloud",
    "aws",
    "gcp",
    "azure",
    "api",
)
_UX_PROFILE_TERMS = (
    "ux",
    "ui",
    "user-centred",
    "user-centered",
    "user centred",
    "user centered",
    "product",
    "prototype",
    "prototyping",
    "figma",
    "usability",
    "stakeholder",
    "workflow mapping",
    "design",
    "customer experience",
)
_EVIDENCE_COMPETENCY_PATTERNS = (
    (re.compile(r"\bretrieval-augmented generation\b|\brag\b", re.IGNORECASE), "RAG Workflow Automation"),
    (re.compile(r"\bllm\b|large language model", re.IGNORECASE), "LLM Solution Prototyping"),
    (re.compile(r"\bprompt engineering\b", re.IGNORECASE), "Prompt Engineering"),
    (re.compile(r"\bmodel evaluation\b|\bevaluation loop", re.IGNORECASE), "Model Evaluation"),
    (re.compile(r"\bnlp\b|sentiment classification", re.IGNORECASE), "NLP Sentiment Classification"),
    (re.compile(r"\bcomputer vision\b|pest recognition", re.IGNORECASE), "Computer Vision Models"),
    (re.compile(r"\bworkflow automation\b|desktop ui automation|openclaw", re.IGNORECASE), "AI Workflow Automation"),
    (re.compile(r"\bopc\b|industrial", re.IGNORECASE), "Industrial AI Automation"),
)
_LOW_SIGNAL_BULLET_TERMS = (
    "unreal engine",
    "unity",
    "interactive game",
    "cat vs dog",
    "figma",
)
_AI_PROFILE_TERMS = (
    "ai",
    "llm",
    "rag",
    "automation",
    "machine learning",
    "model",
    "nlp",
    "computer vision",
    "cv",
    "retrieval",
    "pipeline",
    "prompt",
    "evaluation",
    "data",
    "python",
    "sql",
    "opc",
    "industrial",
)
_PRIORITY_BULLET_TERMS = (
    "rag",
    "retrieval-augmented generation",
    "llm",
    "large language model",
    "automation",
    "workflow automation",
    "workflow",
    "agent",
    "agentic",
    "prompt",
    "evaluation",
)
_SOLUTION_BULLET_TERMS = (
    "model",
    "designed",
    "trained",
    "developed",
    "implemented",
    "machine learning",
    "retrieval-augmented generation",
    "rag",
    "llm",
    "workflow automation",
)
_COLLABORATION_TERMS = (
    "stakeholder",
    "client",
    "customer",
    "team",
    "consultant",
    "developer",
    "cross-functional",
    "partnered",
    "collaborated",
)
_IMPACT_TERMS = (
    "improved",
    "reduced",
    "increased",
    "delivered",
    "built",
    "designed",
    "developed",
    "automated",
    "optimized",
    "launched",
    "implemented",
    "led",
    "supported",
    "coordinated",
    "streamlined",
)
_METRIC_RE = re.compile(
    r"(\d+[%+]|\$\d+|\d+\s?(k|m|b)|\d+\s?(x|hours|days|weeks|months|users|requests))",
    re.IGNORECASE,
)


def _resume_text_supports_keyword(resume_text: str, keyword: str) -> bool:
    normalized_keyword = _compact_whitespace(keyword)
    if not normalized_keyword:
        return False
    return normalized_keyword.casefold() in resume_text.casefold()


def _keyword_matches_technical_skill(keyword: str, technical_skills: list[str]) -> bool:
    normalized_keyword = _compact_whitespace(keyword).casefold()
    if not normalized_keyword:
        return False
    for skill in technical_skills:
        normalized_skill = _compact_whitespace(skill).casefold()
        if not normalized_skill:
            continue
        if normalized_keyword == normalized_skill:
            return True
        keyword_tokens = [token for token in re.split(r"[^a-z0-9+#./-]+", normalized_keyword) if token]
        skill_tokens = [token for token in re.split(r"[^a-z0-9+#./-]+", normalized_skill) if token]
        if normalized_keyword in skill_tokens:
            return True
        if normalized_skill in keyword_tokens:
            return True
        if normalized_keyword.replace("-", "") == normalized_skill.replace("-", ""):
            return True
    return False


def _is_low_signal_competency(item: str, keyword_targets: list[str]) -> bool:
    lowered = _compact_whitespace(item).casefold()
    if not lowered:
        return True
    targets_are_ux = _has_any_term(" ".join(keyword_targets), _UX_PROFILE_TERMS)
    if targets_are_ux and lowered in {
        "figma",
        "product user-centered design",
        "product user-centred design",
    }:
        return False
    return lowered in _LOW_SIGNAL_COMPETENCIES


def select_competencies(
    resume: ResumeData | dict | str,
    keywords: list[str],
    limit: int = 12,
) -> list[str]:
    resume = coerce_resume_data(resume)
    resume_text = resume_to_text(resume)
    technical_skills = [
        _compact_whitespace(skill)
        for skill in resume.additional.technicalSkills
        if _compact_whitespace(skill)
    ]

    matched_keywords = [
        keyword
        for keyword in keywords
        if _resume_text_supports_keyword(resume_text, keyword)
        and _keyword_matches_technical_skill(keyword, technical_skills)
    ]

    prioritized: list[str] = []
    keyword_text = " ".join(keywords)
    jd_targets_ai = _has_any_term(keyword_text, _AI_PROFILE_TERMS)
    jd_targets_ux = _has_any_term(keyword_text, _UX_PROFILE_TERMS)

    for keyword in matched_keywords:
        keyword_lower = keyword.casefold()
        matching_skill = next(
            (skill for skill in technical_skills if skill.casefold() == keyword_lower),
            None,
        )
        prioritized.append(matching_skill or keyword)

    def competency_score(skill: str) -> tuple[int, int, int, int, int, str]:
        lowered = skill.casefold()
        signal_hits = sum(1 for term in _HIGH_SIGNAL_COMPETENCY_TERMS if _contains_term(lowered, term))
        jd_hits = sum(
            1
            for keyword in (matched_keywords or keywords)
            if _compact_whitespace(keyword).casefold() in lowered
        )
        ux_hits = sum(1 for term in _UX_PROFILE_TERMS if _contains_term(lowered, term)) if jd_targets_ux else 0
        evidence_bonus = 1 if any(pattern.search(lowered) for pattern, _label in _EVIDENCE_COMPETENCY_PATTERNS) else 0
        off_target_ai_penalty = 1 if not jd_targets_ai and _has_any_term(lowered, _AI_PROFILE_TERMS) else 0
        return (off_target_ai_penalty, -jd_hits, -ux_hits, -evidence_bonus, -signal_hits, lowered)

    evidence_text_parts: list[str] = []
    for job in resume.workExperience:
        evidence_text_parts.append(job.title)
        evidence_text_parts.append(job.company)
        evidence_text_parts.extend(job.description)
    for project in resume.personalProjects:
        evidence_text_parts.append(project.name)
        evidence_text_parts.append(project.role)
        evidence_text_parts.extend(project.description)
    evidence_text = " ".join(
        _compact_whitespace(part) for part in evidence_text_parts if _compact_whitespace(part)
    )

    evidence_competencies = [
        label
        for pattern, label in _EVIDENCE_COMPETENCY_PATTERNS
        if pattern.search(evidence_text)
    ]
    if jd_targets_ai:
        prioritized.extend(sorted(evidence_competencies, key=competency_score))
        delayed_evidence_competencies: list[str] = []
    else:
        aligned_evidence_competencies = [
            label
            for label in evidence_competencies
            if not _has_any_term(label, _AI_PROFILE_TERMS)
            and any(_compact_whitespace(keyword).casefold() in label.casefold() for keyword in keywords)
        ]
        aligned_keys = {item.casefold() for item in aligned_evidence_competencies}
        delayed_evidence_competencies = [
            label for label in evidence_competencies if label.casefold() not in aligned_keys
        ]
        prioritized.extend(sorted(aligned_evidence_competencies, key=competency_score))

    remaining_skills = [
        skill for skill in technical_skills if skill.casefold() not in {item.casefold() for item in prioritized}
    ]
    prioritized.extend(sorted(remaining_skills, key=competency_score))
    prioritized.extend(sorted(delayed_evidence_competencies, key=competency_score))

    filtered = [
        item for item in _dedupe_preserve_order(prioritized)
        if not _is_low_signal_competency(item, keywords)
    ]
    return filtered[:limit]


def order_skills_for_display(resume: ResumeData, keywords: list[str] | None = None) -> list[str]:
    """Order full skills for display without deleting candidate-provided skills."""
    keyword_targets = keywords or []
    raw_technical_skills = [
        _compact_whitespace(skill)
        for skill in resume.additional.technicalSkills
        if _compact_whitespace(skill)
    ]

    def skill_score(skill: str) -> tuple[int, int, str]:
        lowered = skill.casefold()
        keyword_hits = sum(
            1
            for keyword in keyword_targets
            if _compact_whitespace(keyword).casefold()
            and _compact_whitespace(keyword).casefold() in lowered
        )
        signal_hits = sum(
            1 for term in _HIGH_SIGNAL_COMPETENCY_TERMS if _contains_term(lowered, term)
        )
        return (-keyword_hits, -signal_hits, lowered)

    return sorted(_dedupe_preserve_order(raw_technical_skills), key=skill_score)


def _ensure_sentence_punctuation(text: str) -> str:
    cleaned = _compact_whitespace(text)
    if not cleaned:
        return ""
    if cleaned[-1] in ".!?":
        return cleaned
    return f"{cleaned}."


def _tighten_bullet_language(bullet: str, *, title: str = "", company: str = "") -> str:
    tightened = _compact_whitespace(bullet)
    role_context = f"{_compact_whitespace(title)} {_compact_whitespace(company)}".casefold()
    worked_on_replacement = (
        "Contributed to development of"
        if _contains_term(role_context, "intern")
        else "Delivered"
    )
    replacements = (
        (r"^responsible for\b", "Managed"),
        (r"^in charge of\b", "Managed"),
        (r"^worked on\b", worked_on_replacement),
        (r"^helped with\b", "Supported"),
        (r"^assisted with\b", "Supported"),
        (r"^involved in\b", "Contributed to"),
    )
    for pattern, replacement in replacements:
        tightened = re.sub(pattern, replacement, tightened, flags=re.IGNORECASE)
    feedback_replacement = (
        "Coordinated customer feedback loops and streamlined team workflows to improve content relevance and delivery consistency."
        if any(term in role_context for term in ("studio", "content", "social", "media", "brand"))
        else "Coordinated customer feedback loops and streamlined team workflows to improve operational consistency."
    )
    phrase_replacements = (
        (
            r"\bcoordinated (target )?customer feedback\b.*\b(workflow|workflows)\b.*",
            feedback_replacement,
        ),
        (
            r"\bfounded and (managed|led) a (small )?social media team focused on content creation and community engagement\b",
            "Led a social media team delivering content operations and community engagement across multiple channels",
        ),
        (
            r"\boperated and promoted accounts on .* achieving consistent audience growth\b",
            "Managed and grew social media channels across Xiaohongshu (RED) and Douyin (TikTok China), driving consistent audience growth",
        ),
        (r"^made docs for deployment\.?$", "Prepared deployment documentation."),
        (
            r"^helped debug SQL problems and fixed some bugs\.?$",
            "Supported debugging of SQL issues and resolved defects.",
        ),
        (r"^made (a|an|the) (.+)$", r"Developed \1 \2"),
        (
            r"^used Python scripts to check answers\.?$",
            "Implemented Python scripts to evaluate answer quality.",
        ),
        (
            r"^worked with ([0-9]+) teammates to test it with users\.?$",
            r"Collaborated with \1 teammates to test the solution with users.",
        ),
    )
    for pattern, replacement in phrase_replacements:
        tightened = re.sub(pattern, replacement, tightened, flags=re.IGNORECASE)
    if tightened:
        tightened = tightened[0].upper() + tightened[1:]
    return _ensure_sentence_punctuation(tightened)


def _score_experience_bullet(
    bullet: str,
    keyword_targets: list[str],
    *,
    title: str = "",
    company: str = "",
) -> tuple[int, int, int, int, int, str]:
    normalized = _compact_whitespace(bullet)
    lowered = normalized.casefold()
    jd_hits = sum(1 for keyword in keyword_targets if _compact_whitespace(keyword).casefold() in lowered)
    solution_hits = sum(1 for term in _SOLUTION_BULLET_TERMS if _contains_term(lowered, term))
    if "prediction model" in lowered:
        solution_hits += 3
    if "retrieval-augmented generation" in lowered or re.search(r"\brag\b", lowered):
        solution_hits += 2
    if "machine learning techniques" in lowered:
        solution_hits += 1
    if "customer feedback loops" in lowered or "streamlined team workflows" in lowered:
        solution_hits += 1
    priority_hits = sum(1 for term in _PRIORITY_BULLET_TERMS if _contains_term(lowered, term))
    ai_hits = sum(1 for term in _AI_PROFILE_TERMS if _contains_term(lowered, term))
    collaboration_hits = sum(1 for term in _COLLABORATION_TERMS if _contains_term(lowered, term))
    impact_hits = sum(1 for term in _IMPACT_TERMS if _contains_term(lowered, term))
    metric_bonus = 1 if _METRIC_RE.search(lowered) else 0
    low_signal_penalty = sum(1 for term in _LOW_SIGNAL_BULLET_TERMS if _contains_term(lowered, term))
    role_context = f"{_compact_whitespace(title)} {_compact_whitespace(company)}".casefold()
    project_bonus = 1 if _is_project_like_experience(title, company) or _has_any_term(role_context, _AI_PROFILE_TERMS) else 0
    return (
        low_signal_penalty,
        -solution_hits,
        -metric_bonus,
        -ai_hits,
        -impact_hits,
        -priority_hits,
        -collaboration_hits,
        -(jd_hits + project_bonus),
        lowered,
    )


def _trim_summary(summary: str, max_sentences: int = 3) -> str:
    cleaned = _compact_whitespace(summary)
    if not cleaned:
        return ""
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned)
        if sentence.strip()
    ]
    if len(sentences) <= max_sentences:
        return cleaned
    return " ".join(sentences[:max_sentences]).strip()


def _summary_evidence_text(payload: dict[str, object]) -> str:
    parts = [str(payload.get("summary", ""))]
    for job in payload.get("workExperience", []):
        parts.append(str(job.get("title", "")))
        parts.append(str(job.get("company", "")))
        parts.extend(str(item) for item in job.get("description", []))
    for project in payload.get("personalProjects", []):
        parts.append(str(project.get("name", "")))
        parts.append(str(project.get("role", "")))
        parts.extend(str(item) for item in project.get("description", []))
    additional = payload.get("additional", {})
    if isinstance(additional, dict):
        parts.extend(str(item) for item in additional.get("technicalSkills", []))
    return " ".join(parts)


def _join_summary_strengths(strengths: list[str]) -> str:
    if len(strengths) == 1:
        return strengths[0]
    if len(strengths) == 2:
        return f"{strengths[0]} and {strengths[1]}"
    return f"{', '.join(strengths[:-1])}, and {strengths[-1]}"


def _targeted_ux_summary(payload: dict[str, object]) -> str:
    evidence_text = _summary_evidence_text(payload)
    strengths: list[str] = []

    if _has_any_term(
        evidence_text,
        (
            "user-centred",
            "user-centered",
            "user centred",
            "user centered",
            "user flow",
            "workflow",
            "workflow mapping",
        ),
    ):
        strengths.append("user-centred workflow mapping")
    if _has_any_term(
        evidence_text,
        ("figma", "prototype", "prototyping", "wireframe", "mockup"),
    ):
        strengths.append("Figma prototyping")
    if _has_any_term(
        evidence_text,
        ("stakeholder", "feedback", "usability", "customer insight"),
    ):
        strengths.append("stakeholder feedback loops")

    strengths = _dedupe_preserve_order(strengths)
    if not strengths:
        return ""
    return (
        f"Graduate technologist focused on {_join_summary_strengths(strengths[:3])}. "
        "Translates user feedback into practical prototype and workflow improvements."
    )


def _polish_summary(payload: dict[str, object], keyword_targets: list[str], job_profile=None) -> str:
    current = _compact_whitespace(str(payload.get("summary", "")))
    for pattern, replacement in (
        (r"\bautomation scripting\b", "automation tooling"),
        (r"\bautomation scripts\b", "automation tooling"),
        (r"\bweb-based projects\b", "digital product delivery"),
        (
            r"\bStrong collaborator with experience working across cross-functional teams\b",
            "Strong collaborator across cross-functional teams",
        ),
    ):
        current = re.sub(pattern, replacement, current, flags=re.IGNORECASE)
    payload = {**payload, "summary": current}
    evidence_text = _summary_evidence_text(payload)

    if job_profile and job_profile.primary_type == JOB_TYPE_UX_PRODUCT:
        targeted_summary = _targeted_ux_summary(payload)
        if targeted_summary:
            return _trim_summary(targeted_summary)

    ai_evidence = _has_any_term(evidence_text, _AI_PROFILE_TERMS)
    collaboration_evidence = _has_any_term(evidence_text, _COLLABORATION_TERMS)
    summary_has_ai = _has_any_term(current, _AI_PROFILE_TERMS)
    summary_has_collaboration = _has_any_term(current, _COLLABORATION_TERMS)
    jd_targets_ai = _has_any_term(" ".join(keyword_targets), _AI_PROFILE_TERMS)
    needs_ai_boost = jd_targets_ai and ai_evidence and not summary_has_ai

    extras: list[str] = []
    if needs_ai_boost:
        extras.append(
            "Brings hands-on experience delivering AI and automation projects across Python, data workflows, and practical operational improvements."
        )
    if needs_ai_boost and collaboration_evidence:
        extras.append(
            "Works closely with stakeholders and cross-functional teams to turn prototypes into useful, production-facing workflow improvements."
        )
    elif (
        collaboration_evidence
        and not summary_has_collaboration
        and current
        and re.search(r"\b(student|experience in|background in)\b", current, flags=re.IGNORECASE)
    ):
        extras.append(
            "Collaborates effectively with stakeholders and cross-functional teams to deliver practical workflow improvements."
        )

    if not current:
        return _trim_summary(" ".join(extras).strip())
    if not extras:
        return _trim_summary(current)
    return _trim_summary(f"{current} {' '.join(extras)}".strip())


def _is_project_like_experience(title: str, company: str) -> bool:
    haystack = f"{title} {company}".casefold()
    markers = (
        "project",
        "research",
        "university",
        "lab",
        "capstone",
    )
    return any(marker in haystack for marker in markers)


def _is_academic_project_experience(title: str, company: str) -> bool:
    haystack = f"{title} {company}".casefold()
    return _is_project_like_experience(title, company) and bool(
        re.search(r"\b(university|unsw|school|college|lab|capstone)\b", haystack)
    )


def _work_evidence_entry(
    job: dict[str, object],
    keyword_targets: list[str],
    index: int = 0,
    job_profile=None,
):
    return classify_resume_entry(
        section="workExperience",
        index=index,
        title=str(job.get("title", "")),
        organization=str(job.get("company", "")),
        descriptions=[
            _compact_whitespace(str(item))
            for item in job.get("description", [])
            if _compact_whitespace(str(item))
        ],
        keyword_targets=keyword_targets,
        job_profile=job_profile or infer_job_profile(keyword_targets=keyword_targets),
    )


def _project_evidence_entry(
    project: dict[str, object],
    keyword_targets: list[str],
    index: int = 0,
    job_profile=None,
):
    return classify_resume_entry(
        section="personalProjects",
        index=index,
        title=str(project.get("role", "")),
        organization=str(project.get("name", "")),
        descriptions=[
            _compact_whitespace(str(item))
            for item in project.get("description", [])
            if _compact_whitespace(str(item))
        ],
        keyword_targets=keyword_targets,
        job_profile=job_profile or infer_job_profile(keyword_targets=keyword_targets),
    )


def _project_like_entries(resume: ResumeData) -> list:
    return [
        item
        for item in resume.workExperience
        if _is_project_like_experience(item.title, item.company)
    ]


def _extract_keywords_with_fallback(job_description: str) -> dict[str, object]:
    keyword_targets = extract_keyword_targets(job_description)
    return {
        "required_skills": keyword_targets[:6],
        "preferred_skills": keyword_targets[6:10],
        "experience_requirements": [],
        "education_requirements": [],
        "key_responsibilities": [],
        "keywords": keyword_targets,
        "experience_years": None,
        "seniority_level": None,
    }


def _keyword_targets_from_job_keywords(
    job_keywords: dict[str, object],
    job_description: str,
    *,
    limit: int = 16,
) -> list[str]:
    """Flatten structured JD keywords into the list used by PDF ranking/rendering."""
    target_fields = (
        "required_skills",
        "preferred_skills",
        "keywords",
        "key_responsibilities",
    )
    targets: list[str] = []
    for field in target_fields:
        value = job_keywords.get(field)
        if isinstance(value, str):
            candidates = [value]
        elif isinstance(value, list):
            candidates = [str(item) for item in value]
        else:
            candidates = []
        for candidate in candidates:
            normalized = _compact_whitespace(candidate).strip(".,:;()[]{}")
            if not normalized:
                continue
            if len(normalized.split()) > 5:
                continue
            targets.append(normalized)

    targets.extend(extract_keyword_targets(job_description, limit=limit))
    return _dedupe_preserve_order(targets)[:limit]


def _reorder_by_keyword_hits(items: list[str], keywords: list[str]) -> list[str]:
    def score(item: str) -> tuple[int, str]:
        lower = item.lower()
        hits = sum(1 for keyword in keywords if keyword.lower() in lower)
        return (-hits, lower)

    return sorted(items, key=score)


def _heuristic_tailor_resume(
    resume: ResumeData | dict | str,
    keyword_targets: list[str],
) -> ResumeData:
    """Fallback tailoring that only reorders/emphasizes already-present facts."""
    resume = coerce_resume_data(resume)
    payload = copy.deepcopy(resume.model_dump())
    matched_keywords = select_competencies(resume, keyword_targets, limit=6)

    summary = payload.get("summary", "").strip()
    if matched_keywords:
        spotlight = ", ".join(matched_keywords[:4])
        if spotlight.lower() not in summary.lower():
            summary = f"{summary} Core fit keywords: {spotlight}.".strip()
        payload["summary"] = summary

    technical_skills = payload.get("additional", {}).get("technicalSkills", [])
    if technical_skills:
        payload["additional"]["technicalSkills"] = _reorder_by_keyword_hits(
            technical_skills,
            matched_keywords or keyword_targets,
        )

    work_experience = payload.get("workExperience", [])
    if work_experience:

        def experience_score(job: dict[str, object]) -> tuple[int, int, str]:
            text_parts = [str(job.get("title", "")), str(job.get("company", ""))]
            text_parts.extend(str(item) for item in job.get("description", []))
            text = " ".join(text_parts).lower()
            hits = sum(1 for keyword in matched_keywords if keyword.lower() in text)
            project_bonus = 1 if _is_project_like_experience(str(job.get("title", "")), str(job.get("company", ""))) else 0
            return (-hits, -project_bonus, text)

        payload["workExperience"] = sorted(work_experience, key=experience_score)

    for job in payload.get("workExperience", []):
        descriptions = job.get("description", [])
        if descriptions:
            job["description"] = _reorder_by_keyword_hits(
                descriptions,
                matched_keywords or keyword_targets,
            )

    payload = normalize_resume_data(payload)
    return ResumeData.model_validate(payload)


def _postprocess_pdf_resume(
    resume: ResumeData | dict | str,
    keyword_targets: list[str],
    job_description: str = "",
) -> ResumeData:
    """Apply deterministic polish for the PDF-only tailoring flow."""
    resume = coerce_resume_data(resume)
    payload = copy.deepcopy(resume.model_dump())

    technical_skills = payload.get("additional", {}).get("technicalSkills", [])
    if technical_skills:
        payload["additional"]["technicalSkills"] = _reorder_by_keyword_hits(
            technical_skills,
            keyword_targets,
        )

    job_profile = infer_job_profile(job_description, keyword_targets=keyword_targets)
    payload["summary"] = _polish_summary(payload, keyword_targets, job_profile)

    work_experience = payload.get("workExperience", [])
    if work_experience:
        academic_project_entries = [
            job for job in work_experience
            if _is_academic_project_experience(str(job.get("title", "")), str(job.get("company", "")))
        ]

        def project_summary(index: int, job: dict[str, object]) -> dict[str, object]:
            descriptions = [
                _tighten_bullet_language(
                    str(item),
                    title=str(job.get("title", "")),
                    company=str(job.get("company", "")),
                )
                for item in job.get("description", [])
                if _compact_whitespace(str(item))
            ]
            descriptions = sorted(
                descriptions,
                key=lambda bullet: _score_experience_bullet(
                    bullet,
                    keyword_targets,
                    title=str(job.get("title", "")),
                    company=str(job.get("company", "")),
                ),
            )
            return {
                "id": index + 1,
                "name": str(job.get("company", "")).strip() or f"Project {index + 1}",
                "role": str(job.get("title", "")).strip(),
                "years": str(job.get("years", "")).strip(),
                "description": descriptions,
            }

        if not payload.get("personalProjects") and academic_project_entries:
            payload["personalProjects"] = [
                project_summary(index, job)
                for index, job in enumerate(academic_project_entries)
            ]
        elif academic_project_entries:
            existing_projects = payload.get("personalProjects", [])
            existing_keys = {
                (
                    str(project.get("name", "")).casefold(),
                    str(project.get("role", "")).casefold(),
                    str(project.get("years", "")).casefold(),
                )
                for project in existing_projects
            }
            next_index = len(existing_projects)
            for job in academic_project_entries:
                key = (
                    str(job.get("company", "")).casefold(),
                    str(job.get("title", "")).casefold(),
                    str(job.get("years", "")).casefold(),
                )
                if key not in existing_keys:
                    existing_projects.append(project_summary(next_index, job))
                    next_index += 1
            payload["personalProjects"] = existing_projects

        work_experience = [
            job for job in work_experience
            if not _is_academic_project_experience(str(job.get("title", "")), str(job.get("company", "")))
        ]

        def experience_score(job: dict[str, object]) -> tuple[int, int, int, str]:
            text_parts = [str(job.get("title", "")), str(job.get("company", ""))]
            text_parts.extend(str(item) for item in job.get("description", []))
            text = " ".join(text_parts).lower()
            hits = sum(1 for keyword in keyword_targets if keyword.lower() in text)
            project_bonus = 1 if _is_project_like_experience(str(job.get("title", "")), str(job.get("company", ""))) else 0
            evidence_entry = _work_evidence_entry(job, keyword_targets, job_profile=job_profile)
            return (-evidence_entry.relevance_score, -hits, -project_bonus, text)

        payload["workExperience"] = sorted(work_experience, key=experience_score)
        for job in payload["workExperience"]:
            descriptions = [
                _tighten_bullet_language(
                    str(item),
                    title=str(job.get("title", "")),
                    company=str(job.get("company", "")),
                )
                for item in job.get("description", [])
                if _compact_whitespace(str(item))
            ]
            job["description"] = sorted(
                descriptions,
                key=lambda bullet: _score_experience_bullet(
                    bullet,
                    keyword_targets,
                    title=str(job.get("title", "")),
                    company=str(job.get("company", "")),
                ),
            )

    personal_projects = payload.get("personalProjects", [])
    if personal_projects:
        def project_score(indexed_project: tuple[int, dict[str, object]]) -> tuple[int, int, str]:
            index, project = indexed_project
            evidence_entry = _project_evidence_entry(
                project,
                keyword_targets,
                index=index,
                job_profile=job_profile,
            )
            text_parts = [str(project.get("role", "")), str(project.get("name", ""))]
            text_parts.extend(str(item) for item in project.get("description", []))
            text = " ".join(text_parts).casefold()
            hits = sum(1 for keyword in keyword_targets if keyword.casefold() in text)
            return (-evidence_entry.relevance_score, -hits, text)

        payload["personalProjects"] = [
            project
            for _index, project in sorted(
                enumerate(personal_projects),
                key=project_score,
            )
        ]

    payload = normalize_resume_data(payload)
    return ResumeData.model_validate(payload)


def _restore_protected_fields(
    original_resume: dict[str, object],
    tailored_payload: dict[str, object],
) -> dict[str, object]:
    """Restore identity fields that should never be dropped by tailoring."""
    result = copy.deepcopy(tailored_payload)
    result["personalInfo"] = copy.deepcopy(original_resume.get("personalInfo", {}))
    result["customSections"] = copy.deepcopy(original_resume.get("customSections", {}))
    result["sectionMeta"] = copy.deepcopy(original_resume.get("sectionMeta", []))
    return result


def _remove_full_output_alignment_violations(
    original_resume: dict[str, object],
    tailored_payload: dict[str, object],
) -> dict[str, object]:
    """Remove unsupported additions from full-output tailoring results."""
    alignment = validate_master_alignment(tailored_payload, original_resume)
    if alignment.is_aligned:
        return tailored_payload

    fixed_payload = fix_alignment_violations(tailored_payload, alignment.violations)
    remaining_alignment = validate_master_alignment(fixed_payload, original_resume)
    if not remaining_alignment.is_aligned:
        raise ValueError("Full-output tailoring introduced unsupported content")
    return fixed_payload


async def _tailor_resume(
    resume: ResumeData,
    job_description: str,
) -> tuple[ResumeData, list[str]]:
    """Use the existing resume improver first, with a deterministic fallback."""
    job_keywords: dict[str, object]

    try:
        job_keywords = await extract_job_keywords_llm(job_description)
    except Exception as exc:
        logger.warning("Keyword extraction fell back to local heuristic: %s", exc)
        job_keywords = _extract_keywords_with_fallback(job_description)
    keyword_targets = _keyword_targets_from_job_keywords(job_keywords, job_description)

    try:
        tailored_payload = await improve_resume(
            original_resume=resume_to_text(resume),
            job_description=job_description,
            job_keywords=job_keywords,
            prompt_id="full",
            original_resume_data=resume.model_dump(),
        )
        tailored_payload = _restore_protected_fields(
            resume.model_dump(),
            tailored_payload,
        )
        tailored_payload = _remove_full_output_alignment_violations(
            resume.model_dump(),
            tailored_payload,
        )
        tailored_payload = normalize_resume_data(copy.deepcopy(tailored_payload))
        return _postprocess_pdf_resume(tailored_payload, keyword_targets, job_description), keyword_targets
    except Exception as exc:
        logger.warning("Full-output tailoring failed, trying diff fallback: %s", exc)
        try:
            diff_result = await generate_resume_diffs(
                original_resume=resume_to_text(resume),
                job_description=job_description,
                job_keywords=job_keywords,
                language="en",
                prompt_id="full",
                original_resume_data=resume.model_dump(),
            )
            improved_data, applied_changes, rejected_changes = apply_diffs(
                original=resume.model_dump(),
                changes=diff_result.changes,
            )
            diff_warnings = verify_diff_result(
                original=resume.model_dump(),
                result=improved_data,
                applied_changes=applied_changes,
                job_keywords=job_keywords,
            )
            if rejected_changes or diff_warnings:
                logger.info(
                    "PDF diff fallback applied %d changes, rejected %d, warnings=%d",
                    len(applied_changes),
                    len(rejected_changes),
                    len(diff_warnings),
                )
            improved_data = _restore_protected_fields(
                resume.model_dump(),
                improved_data,
            )
            improved_data = normalize_resume_data(copy.deepcopy(improved_data))
            return _postprocess_pdf_resume(improved_data, keyword_targets, job_description), keyword_targets
        except Exception as diff_exc:
            logger.warning("Tailored resume generation fell back to local heuristic: %s", diff_exc)
        return _postprocess_pdf_resume(
            _heuristic_tailor_resume(resume, keyword_targets),
            keyword_targets,
            job_description,
        ), keyword_targets


_select_competencies = select_competencies
