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
}


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

    # Then fill with the candidate's real technical skills, ordered by JD overlap.
    remaining_skills = [
        skill for skill in technical_skills if skill.casefold() not in {item.casefold() for item in prioritized}
    ]
    prioritized.extend(_reorder_by_keyword_hits(remaining_skills, matched_keywords or keywords))

    filtered = [
        item for item in _dedupe_preserve_order(prioritized)
        if item.casefold() not in _LOW_SIGNAL_COMPETENCIES
    ]
    return filtered[:limit]


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


def _render_skills(resume: ResumeData) -> str:
    groups = [
        ("Technical", resume.additional.technicalSkills),
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
        "{{SKILLS}}": _render_skills(normalized_resume),
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

    work_experience = payload.get("workExperience", [])
    if work_experience:
        project_entries = [
            job for job in work_experience
            if _is_project_like_experience(str(job.get("title", "")), str(job.get("company", "")))
        ]

        if not payload.get("personalProjects") and project_entries:
            payload["personalProjects"] = [
                {
                    "id": index + 1,
                    "name": str(job.get("company", "")).strip() or f"Project {index + 1}",
                    "role": str(job.get("title", "")).strip(),
                    "years": str(job.get("years", "")).strip(),
                    "description": list(job.get("description", []))[:4],
                }
                for index, job in enumerate(project_entries)
            ]

        def experience_score(job: dict[str, object]) -> tuple[int, int, str]:
            text_parts = [str(job.get("title", "")), str(job.get("company", ""))]
            text_parts.extend(str(item) for item in job.get("description", []))
            text = " ".join(text_parts).lower()
            hits = sum(1 for keyword in keyword_targets if keyword.lower() in text)
            project_bonus = 1 if _is_project_like_experience(str(job.get("title", "")), str(job.get("company", ""))) else 0
            return (-hits, -project_bonus, text)

        payload["workExperience"] = sorted(work_experience, key=experience_score)

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
