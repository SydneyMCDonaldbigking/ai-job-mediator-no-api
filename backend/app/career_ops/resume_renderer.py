"""HTML resume renderer for structured resume data.

This module is intentionally UI-only: it does not parse uploads, call an LLM,
or tailor candidate facts. It receives a ResumeData-compatible object and
renders it through one of the available resume templates.
"""

from __future__ import annotations

import logging
import os
import random
from html import escape
from pathlib import Path

from app.career_ops.evaluator import coerce_resume_data, extract_keyword_targets
from app.career_ops.resume_tailoring import (
    order_skills_for_display,
    select_competencies,
)
from app.career_ops.resume_text import _compact_whitespace, normalize_text_for_ats
from app.schemas.models import ResumeData

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"
_TEMPLATE_FILES = {
    "modern": _TEMPLATE_DIR / "cv_template.html",
    "executive": _TEMPLATE_DIR / "cv_template_executive.html",
    "compact": _TEMPLATE_DIR / "cv_template_compact.html",
}
_TEMPLATE_PATH = _TEMPLATE_FILES["modern"]


def _render_competencies(resume: ResumeData | dict | str, keywords: list[str]) -> str:
    items = select_competencies(resume, keywords) or [
        "Targeted resume generated from the supplied job description"
    ]
    return "\n".join(
        f'<span class="competency-tag">{escape(_compact_whitespace(item))}</span>'
        for item in items
        if _compact_whitespace(item)
    )


def _render_section(title: str, body: str) -> str:
    clean_body = _compact_whitespace(body)
    if not clean_body:
        return ""
    return f"""
<div class="section">
  <div class="section-title">{escape(_compact_whitespace(title))}</div>
  {body}
</div>
""".strip()


def _render_experience(resume: ResumeData) -> str:
    if not resume.workExperience:
        return '<div class="job"><div class="job-role">No structured experience provided.</div></div>'

    jobs: list[str] = []
    for item in resume.workExperience:
        bullets = "\n".join(
            f"<li>{escape(_compact_whitespace(bullet))}</li>"
            for bullet in item.description
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


def _render_projects(resume: ResumeData | dict | str) -> str:
    resume = coerce_resume_data(resume)
    if not resume.personalProjects:
        return '<div class="project"><div class="project-desc">No project data provided.</div></div>'

    projects: list[str] = []
    for item in resume.personalProjects:
        bullets = "\n".join(
            f"<li>{escape(_compact_whitespace(bullet))}</li>"
            for bullet in item.description
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
        return ""

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
    groups = [
        ("Technical", order_skills_for_display(resume, keywords)),
        ("Languages", resume.additional.languages),
        ("Awards", resume.additional.awards),
    ]
    items: list[str] = []
    for label, values in groups:
        clean_values = [
            escape(_compact_whitespace(value))
            for value in values
            if _compact_whitespace(value)
        ]
        if clean_values:
            items.append(
                f'<div class="skill-item"><span class="skill-category">{label}:</span> {", ".join(clean_values)}</div>'
            )
    return "\n".join(items) or '<div class="skill-item">No additional skills provided.</div>'


def _select_resume_template(template_name: str | None = None) -> tuple[str, Path]:
    requested = _compact_whitespace(template_name or os.environ.get("RESUME_TEMPLATE", ""))
    requested_key = requested.casefold()
    if requested_key and requested_key != "random":
        if requested_key in _TEMPLATE_FILES:
            return requested_key, _TEMPLATE_FILES[requested_key]
        logger.warning(
            "Unknown resume template '%s'; using a random template from %s",
            requested,
            ", ".join(sorted(_TEMPLATE_FILES)),
        )

    selected_key = random.choice(tuple(_TEMPLATE_FILES))
    return selected_key, _TEMPLATE_FILES[selected_key]


def render_resume_html(
    resume: ResumeData | dict | str,
    job_description: str,
    keywords: list[str] | None = None,
    *,
    template_name: str | None = None,
) -> str:
    """Render a structured resume into an ATS-focused HTML template."""
    normalized_resume = coerce_resume_data(resume)
    keyword_targets = keywords or extract_keyword_targets(job_description)
    selected_template, template_path = _select_resume_template(template_name)
    template = template_path.read_text(encoding="utf-8")

    personal = normalized_resume.personalInfo
    replacements = {
        "{{LANG}}": "en",
        "{{PAGE_WIDTH}}": "8.27in",
        "{{TEMPLATE_NAME}}": escape(selected_template),
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
        "{{CERTIFICATIONS_SECTION}}": _render_section(
            "Certifications",
            _render_certifications(normalized_resume),
        ),
        "{{SKILLS}}": _render_skills(normalized_resume, keyword_targets),
    }

    html = template
    for placeholder, value in replacements.items():
        html = html.replace(placeholder, value)

    normalized_html, _ = normalize_text_for_ats(html)
    return normalized_html
