"""ATS-friendly HTML to PDF generator inspired by career-ops."""

from __future__ import annotations

import copy
import logging
import os
import re
import sys
from html import escape
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.career_ops.evaluator import (
    coerce_resume_data,
    extract_keyword_targets,
    resume_to_text,
)
from app.schemas.models import ResumeData, TailoredPDFResult, normalize_resume_data
from app.services.improver import apply_diffs
from app.services.improver import extract_job_keywords as extract_job_keywords_llm
from app.services.improver import generate_resume_diffs
from app.services.improver import improve_resume
from app.services.improver import verify_diff_result

logger = logging.getLogger(__name__)

_TEMPLATE_PATH = Path(__file__).parent / "templates" / "cv_template.html"
_ZERO_WIDTH_RE = re.compile(r"[\u200B\u200C\u200D\u2060\uFEFF]")
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
_METRIC_RE = re.compile(r"(\d+[%+]|\$\d+|\d+\s?(k|m|b)|\d+\s?(x|hours|days|weeks|months|users|requests))", re.IGNORECASE)


class CareerOpsPDFError(Exception):
    """Raised when tailored PDF generation fails."""


def normalize_text_for_ats(text: str) -> tuple[str, dict[str, int]]:
    """Replace Unicode characters that commonly break ATS parsing."""
    replacements = {
        "em_dash": 0,
        "en_dash": 0,
        "smart_double_quote": 0,
        "smart_single_quote": 0,
        "ellipsis": 0,
        "zero_width": 0,
        "nbsp": 0,
    }

    normalized = text
    for old, new, key in (
        ("\u2014", "-", "em_dash"),
        ("\u2013", "-", "en_dash"),
        ("\u2026", "...", "ellipsis"),
        ("\u00a0", " ", "nbsp"),
    ):
        count = normalized.count(old)
        if count:
            normalized = normalized.replace(old, new)
            replacements[key] += count

    smart_double_count = sum(normalized.count(ch) for ch in ('\u201c', '\u201d', '\u201e', '\u201f'))
    if smart_double_count:
        for ch in ('\u201c', '\u201d', '\u201e', '\u201f'):
            normalized = normalized.replace(ch, '"')
        replacements["smart_double_quote"] = smart_double_count

    smart_single_count = sum(normalized.count(ch) for ch in ('\u2018', '\u2019', '\u201a', '\u201b'))
    if smart_single_count:
        for ch in ('\u2018', '\u2019', '\u201a', '\u201b'):
            normalized = normalized.replace(ch, "'")
        replacements["smart_single_quote"] = smart_single_count

    zero_width_matches = _ZERO_WIDTH_RE.findall(normalized)
    if zero_width_matches:
        replacements["zero_width"] = len(zero_width_matches)
        normalized = _ZERO_WIDTH_RE.sub("", normalized)

    return normalized, replacements


def _compact_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).strip()


def _join_contact(parts: list[str]) -> str:
    safe_parts = [escape(_compact_whitespace(part)) for part in parts if _compact_whitespace(part)]
    return " <span class=\"separator\">|</span> ".join(safe_parts) or "Not provided"


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = _compact_whitespace(item)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


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


def _select_competencies(
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

    # Prefer JD-aligned technologies that are actually supported by the resume.
    for keyword in matched_keywords:
        keyword_lower = keyword.casefold()
        matching_skill = next(
            (skill for skill in technical_skills if skill.casefold() == keyword_lower),
            None,
        )
        prioritized.append(matching_skill or keyword)

    def competency_score(skill: str) -> tuple[int, int, int, str]:
        lowered = skill.casefold()
        signal_hits = sum(1 for term in _HIGH_SIGNAL_COMPETENCY_TERMS if term in lowered)
        jd_hits = sum(1 for keyword in (matched_keywords or keywords) if keyword.casefold() in lowered)
        evidence_bonus = 1 if any(pattern.search(lowered) for pattern, _label in _EVIDENCE_COMPETENCY_PATTERNS) else 0
        return (-evidence_bonus, -signal_hits, -jd_hits, lowered)

    evidence_text_parts: list[str] = []
    for job in resume.workExperience:
        evidence_text_parts.append(job.title)
        evidence_text_parts.append(job.company)
        evidence_text_parts.extend(job.description)
    for project in resume.personalProjects:
        evidence_text_parts.append(project.name)
        evidence_text_parts.append(project.role)
        evidence_text_parts.extend(project.description)
    evidence_text = " ".join(_compact_whitespace(part) for part in evidence_text_parts if _compact_whitespace(part))

    evidence_competencies = [
        label
        for pattern, label in _EVIDENCE_COMPETENCY_PATTERNS
        if pattern.search(evidence_text)
    ]
    prioritized.extend(
        sorted(
            evidence_competencies,
            key=competency_score,
        )
    )

    # Then fill with the candidate's real technical skills, ordered by relevance and signal.
    remaining_skills = [
        skill for skill in technical_skills if skill.casefold() not in {item.casefold() for item in prioritized}
    ]
    prioritized.extend(sorted(remaining_skills, key=competency_score))

    filtered = [
        item for item in _dedupe_preserve_order(prioritized)
        if item.casefold() not in _LOW_SIGNAL_COMPETENCIES
    ]
    return filtered[:limit]


def _has_any_term(text: str, terms: tuple[str, ...]) -> bool:
    lowered = _compact_whitespace(text).casefold()
    return any(term in lowered for term in terms)


def _tighten_bullet_language(bullet: str) -> str:
    tightened = _compact_whitespace(bullet)
    replacements = (
        (r"^responsible for\b", "Managed"),
        (r"^in charge of\b", "Managed"),
        (r"^worked on\b", "Delivered"),
        (r"^helped with\b", "Supported"),
        (r"^assisted with\b", "Supported"),
        (r"^involved in\b", "Contributed to"),
    )
    for pattern, replacement in replacements:
        tightened = re.sub(pattern, replacement, tightened, flags=re.IGNORECASE)
    phrase_replacements = (
        (
            r"\bcoordinated (target )?customer feedback\b.*\b(workflow|workflows)\b.*",
            "Coordinated customer feedback loops and streamlined team workflows to improve content relevance and delivery consistency.",
        ),
        (
            r"\bfounded and (managed|led) a (small )?social media team focused on content creation and community engagement\b",
            "Led a social media team delivering content operations and community engagement across multiple channels",
        ),
        (
            r"\boperated and promoted accounts on .* achieving consistent audience growth\b",
            "Managed and grew social media channels across Xiaohongshu (RED) and Douyin (TikTok China), driving consistent audience growth",
        ),
    )
    for pattern, replacement in phrase_replacements:
        tightened = re.sub(pattern, replacement, tightened, flags=re.IGNORECASE)
    return tightened


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
    solution_hits = sum(1 for term in _SOLUTION_BULLET_TERMS if term in lowered)
    if "prediction model" in lowered:
        solution_hits += 3
    if "retrieval-augmented generation" in lowered or re.search(r"\brag\b", lowered):
        solution_hits += 2
    if "machine learning techniques" in lowered:
        solution_hits += 1
    priority_hits = sum(1 for term in _PRIORITY_BULLET_TERMS if term in lowered)
    ai_hits = sum(1 for term in _AI_PROFILE_TERMS if term in lowered)
    collaboration_hits = sum(1 for term in _COLLABORATION_TERMS if term in lowered)
    impact_hits = sum(1 for term in _IMPACT_TERMS if term in lowered)
    metric_bonus = 1 if _METRIC_RE.search(lowered) else 0
    low_signal_penalty = sum(1 for term in _LOW_SIGNAL_BULLET_TERMS if term in lowered)
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


def _polish_summary(payload: dict[str, object], keyword_targets: list[str]) -> str:
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
    work_experience = payload.get("workExperience", [])
    evidence_text_parts = [current]
    for job in work_experience:
        evidence_text_parts.append(str(job.get("title", "")))
        evidence_text_parts.append(str(job.get("company", "")))
        evidence_text_parts.extend(str(item) for item in job.get("description", []))
    evidence_text = " ".join(evidence_text_parts)

    ai_evidence = _has_any_term(evidence_text, _AI_PROFILE_TERMS)
    collaboration_evidence = _has_any_term(evidence_text, _COLLABORATION_TERMS)
    summary_has_ai = _has_any_term(current, _AI_PROFILE_TERMS)
    summary_has_collaboration = _has_any_term(current, _COLLABORATION_TERMS)
    needs_ai_boost = ai_evidence and not summary_has_ai

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
        return " ".join(extras).strip()
    if not extras:
        return current
    return f"{current} {' '.join(extras)}".strip()


def _render_competencies(resume: ResumeData | dict | str, keywords: list[str]) -> str:
    items = _select_competencies(resume, keywords) or [
        "Targeted resume generated from the supplied job description"
    ]
    return "\n".join(
        f'<span class="competency-tag">{escape(_compact_whitespace(item))}</span>'
        for item in items
        if _compact_whitespace(item)
    )


def _render_experience(resume: ResumeData) -> str:
    if not resume.workExperience:
        return '<div class="job"><div class="job-role">No structured experience provided.</div></div>'

    jobs: list[str] = []
    for item in resume.workExperience:
        bullets = "\n".join(
            f"<li>{escape(_compact_whitespace(bullet))}</li>"
            for bullet in item.description[:4]
            if _compact_whitespace(bullet)
        ) or "<li>No bullet points provided.</li>"

        location = (
            f'<div class="job-location">{escape(_compact_whitespace(item.location))}</div>'
            if _compact_whitespace(item.location)
            else ""
        )
        jobs.append(
            f"""
<div class="job">
  <div class="job-header">
    <div class="job-company">{escape(_compact_whitespace(item.company))}</div>
    <div class="job-period">{escape(_compact_whitespace(item.years))}</div>
  </div>
  <div class="job-role">{escape(_compact_whitespace(item.title))}</div>
  {location}
  <ul>{bullets}</ul>
</div>
""".strip()
        )
    return "\n".join(jobs)


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


def _project_like_entries(resume: ResumeData) -> list:
    return [
        item
        for item in resume.workExperience
        if _is_project_like_experience(item.title, item.company)
    ]


def _render_projects(resume: ResumeData | dict | str) -> str:
    resume = coerce_resume_data(resume)
    if not resume.personalProjects:
        return '<div class="project"><div class="project-desc">No project data provided.</div></div>'

    projects: list[str] = []
    for item in resume.personalProjects:
        bullets = "\n".join(
            f"<li>{escape(_compact_whitespace(bullet))}</li>"
            for bullet in item.description[:4]
            if _compact_whitespace(bullet)
        ) or "<li>No project highlights provided.</li>"
        projects.append(
            f"""
<div class="project">
  <div class="project-title">{escape(_compact_whitespace(item.name))} <span class="project-badge">{escape(_compact_whitespace(item.role))}</span></div>
  <div class="project-desc"><ul>{bullets}</ul></div>
  <div class="project-tech">{escape(_compact_whitespace(item.years))}</div>
</div>
""".strip()
        )
    return "\n".join(projects)


def _render_education(resume: ResumeData) -> str:
    if not resume.education:
        return '<div class="edu-item"><div class="edu-title">No education data provided.</div></div>'

    education_items: list[str] = []
    for item in resume.education:
        description = (
            f'<div class="edu-desc">{escape(_compact_whitespace(item.description))}</div>'
            if _compact_whitespace(item.description)
            else ""
        )
        education_items.append(
            f"""
<div class="edu-item">
  <div class="edu-header">
    <div class="edu-title">{escape(_compact_whitespace(item.degree))} <span class="edu-org">@ {escape(_compact_whitespace(item.institution))}</span></div>
    <div class="edu-year">{escape(_compact_whitespace(item.years))}</div>
  </div>
  {description}
</div>
""".strip()
        )
    return "\n".join(education_items)


def _render_certifications(resume: ResumeData) -> str:
    certifications = resume.additional.certificationsTraining
    if not certifications:
        return '<div class="cert-item"><div class="cert-title">No certifications provided.</div></div>'

    return "\n".join(
        f"""
<div class="cert-item">
  <div class="cert-title">{escape(_compact_whitespace(certification))}</div>
  <div class="cert-year"></div>
</div>
""".strip()
        for certification in certifications
        if _compact_whitespace(certification)
    )


def _render_skills(resume: ResumeData, keywords: list[str] | None = None) -> str:
    technical_skills = _select_competencies(resume, keywords or [], limit=10)
    groups = [
        ("Technical", technical_skills),
        ("Languages", resume.additional.languages),
        ("Awards", resume.additional.awards),
    ]
    items: list[str] = []
    for label, values in groups:
        clean_values = [escape(_compact_whitespace(value)) for value in values if _compact_whitespace(value)]
        if clean_values:
            items.append(
                f'<div class="skill-item"><span class="skill-category">{label}:</span> {", ".join(clean_values)}</div>'
            )
    return "\n".join(items) or '<div class="skill-item">No additional skills provided.</div>'


def render_resume_html(
    resume: ResumeData | dict | str,
    job_description: str,
    keywords: list[str] | None = None,
) -> str:
    """Render a structured resume into the local ATS-focused HTML template."""
    normalized_resume = coerce_resume_data(resume)
    keyword_targets = keywords or extract_keyword_targets(job_description)
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")

    personal = normalized_resume.personalInfo
    replacements = {
        "{{LANG}}": "en",
        "{{PAGE_WIDTH}}": "8.27in",
        "{{NAME}}": escape(_compact_whitespace(personal.name) or "Candidate"),
        "{{PHONE}}": escape(_compact_whitespace(personal.phone) or "Phone not provided"),
        "{{EMAIL}}": escape(_compact_whitespace(personal.email) or "Email not provided"),
        "{{LINKEDIN_URL}}": escape(_compact_whitespace(personal.linkedin) or "#"),
        "{{LINKEDIN_DISPLAY}}": escape(_compact_whitespace(personal.linkedin) or "LinkedIn"),
        "{{PORTFOLIO_URL}}": escape(_compact_whitespace(personal.website or personal.github) or "#"),
        "{{PORTFOLIO_DISPLAY}}": escape(_compact_whitespace(personal.website or personal.github) or "Portfolio"),
        "{{LOCATION}}": escape(_compact_whitespace(personal.location) or "Location not provided"),
        "{{SECTION_SUMMARY}}": "Professional Summary",
        "{{SECTION_COMPETENCIES}}": "Core Competencies",
        "{{SECTION_EXPERIENCE}}": "Work Experience",
        "{{SECTION_PROJECTS}}": "Projects",
        "{{SECTION_EDUCATION}}": "Education",
        "{{SECTION_CERTIFICATIONS}}": "Certifications",
        "{{SECTION_SKILLS}}": "Skills",
        "{{SUMMARY_TEXT}}": escape(_compact_whitespace(normalized_resume.summary) or "Summary not provided."),
        "{{COMPETENCIES}}": _render_competencies(normalized_resume, keyword_targets),
        "{{EXPERIENCE}}": _render_experience(normalized_resume),
        "{{PROJECTS}}": _render_projects(normalized_resume),
        "{{EDUCATION}}": _render_education(normalized_resume),
        "{{CERTIFICATIONS}}": _render_certifications(normalized_resume),
        "{{SKILLS}}": _render_skills(normalized_resume, keyword_targets),
    }

    html = template
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    normalized_html, _ = normalize_text_for_ats(html)
    return normalized_html


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
    resume_text = resume_to_text(resume)
    matched_keywords = _select_competencies(resume, keyword_targets, limit=6)

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

    payload["summary"] = _polish_summary(payload, keyword_targets)

    work_experience = payload.get("workExperience", [])
    if work_experience:
        project_entries = [
            job for job in work_experience
            if _is_project_like_experience(str(job.get("title", "")), str(job.get("company", "")))
        ]
        academic_project_entries = [
            job for job in work_experience
            if _is_academic_project_experience(str(job.get("title", "")), str(job.get("company", "")))
        ]

        def project_summary(index: int, job: dict[str, object]) -> dict[str, object]:
            descriptions = [
                _tighten_bullet_language(str(item))
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
                "description": descriptions[:4],
            }

        if not payload.get("personalProjects") and project_entries:
            payload["personalProjects"] = [
                project_summary(index, job)
                for index, job in enumerate(project_entries)
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

        def experience_score(job: dict[str, object]) -> tuple[int, int, str]:
            text_parts = [str(job.get("title", "")), str(job.get("company", ""))]
            text_parts.extend(str(item) for item in job.get("description", []))
            text = " ".join(text_parts).lower()
            hits = sum(1 for keyword in keyword_targets if keyword.lower() in text)
            project_bonus = 1 if _is_project_like_experience(str(job.get("title", "")), str(job.get("company", ""))) else 0
            return (-hits, -project_bonus, text)

        payload["workExperience"] = sorted(work_experience, key=experience_score)
        for job in payload["workExperience"]:
            descriptions = [
                _tighten_bullet_language(str(item))
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


async def _tailor_resume(
    resume: ResumeData,
    job_description: str,
) -> tuple[ResumeData, list[str]]:
    """Use the existing resume improver first, with a deterministic fallback."""
    keyword_targets = extract_keyword_targets(job_description)
    job_keywords: dict[str, object]

    try:
        job_keywords = await extract_job_keywords_llm(job_description)
    except Exception as exc:
        logger.warning("Keyword extraction fell back to local heuristic: %s", exc)
        job_keywords = _extract_keywords_with_fallback(job_description)

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
        tailored_payload = normalize_resume_data(copy.deepcopy(tailored_payload))
        return _postprocess_pdf_resume(tailored_payload, keyword_targets), keyword_targets
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
            return _postprocess_pdf_resume(improved_data, keyword_targets), keyword_targets
        except Exception as diff_exc:
            logger.warning("Tailored resume generation fell back to local heuristic: %s", diff_exc)
        return _postprocess_pdf_resume(
            _heuristic_tailor_resume(resume, keyword_targets),
            keyword_targets,
        ), keyword_targets


def _find_chromium_executable() -> str | None:
    """Find a system Chromium/Chrome/Edge binary."""
    if sys.platform == "win32":
        candidates = [
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Google/Chrome/Application/chrome.exe",
            Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Microsoft/Edge/Application/msedge.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
            Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        ]
    else:
        candidates = [
            Path("/usr/bin/google-chrome"),
            Path("/usr/bin/google-chrome-stable"),
            Path("/usr/bin/chromium"),
            Path("/usr/bin/chromium-browser"),
            Path("/usr/bin/microsoft-edge"),
        ]

    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


async def _launch_browser(playwright, headless: bool = False):
    """Launch Chromium with a system-browser fallback."""
    launch_kwargs = {"headless": headless}
    try:
        return await playwright.chromium.launch(**launch_kwargs)
    except PlaywrightError as exc:
        if "Executable doesn't exist" not in str(exc):
            raise
        executable_path = _find_chromium_executable()
        if not executable_path:
            raise CareerOpsPDFError(
                "Playwright Chromium is missing and no system Chrome/Edge executable was found."
            ) from exc
        launch_kwargs["executable_path"] = executable_path
        return await playwright.chromium.launch(**launch_kwargs)


def _slugify_filename(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "tailored-resume"


def _pdf_format(page_size: str) -> str:
    return "Letter" if page_size.upper() == "LETTER" else "A4"


async def generate_tailored_resume_pdf(
    resume: ResumeData | dict | str,
    job_description: str,
    page_size: str = "A4",
    *,
    headless: bool = False,
) -> TailoredPDFResult:
    """Tailor a resume to the JD, render HTML, and return PDF bytes.

    ``headless`` defaults to ``False`` to match the requested visual output
    workflow from this task.
    """
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    normalized_resume = coerce_resume_data(resume)
    tailored_resume, keyword_targets = await _tailor_resume(
        resume=normalized_resume,
        job_description=job_description,
    )
    html = render_resume_html(
        resume=tailored_resume,
        job_description=job_description,
        keywords=keyword_targets,
    )

    try:
        async with async_playwright() as playwright:
            browser = await _launch_browser(playwright, headless=headless)
            try:
                page = await browser.new_page(viewport={"width": 1280, "height": 1700})
                await page.set_content(html, wait_until="networkidle")
                await page.emulate_media(media="screen")
                await page.evaluate("document.fonts.ready")
                pdf_bytes = await page.pdf(
                    format=_pdf_format(page_size),
                    print_background=True,
                    margin={
                        "top": "0.55in",
                        "right": "0.55in",
                        "bottom": "0.55in",
                        "left": "0.55in",
                    },
                    prefer_css_page_size=False,
                )
            finally:
                await browser.close()
    except PlaywrightError as exc:
        raise CareerOpsPDFError(f"Playwright PDF generation failed: {exc}") from exc

    filename = f"{_slugify_filename(tailored_resume.personalInfo.name)}-tailored.pdf"
    return TailoredPDFResult(
        filename=filename,
        pdf_bytes=pdf_bytes,
        tailored_resume=tailored_resume,
        keyword_targets=keyword_targets,
    )
