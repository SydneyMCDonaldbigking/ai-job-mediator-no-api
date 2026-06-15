"""PDF orchestration for tailored resumes.

The upload/parser path produces structured resume JSON. Tailoring modules adjust
that JSON. Renderer modules turn that JSON into HTML. This file only coordinates
HTML-to-PDF rendering and keeps the legacy public imports stable.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

from app.career_ops.evaluator import coerce_resume_data
from app.career_ops.resume_renderer import (
    _TEMPLATE_FILES,
    _TEMPLATE_PATH,
    _render_competencies,
    _render_experience,
    _render_projects,
    _render_skills,
    _select_resume_template,
    render_resume_html,
)
from app.career_ops.resume_tailoring import (
    _extract_keywords_with_fallback,
    _heuristic_tailor_resume,
    _keyword_targets_from_job_keywords,
    _postprocess_pdf_resume,
    _reorder_by_keyword_hits,
    _restore_protected_fields,
    _select_competencies,
    _tailor_resume,
)
from app.career_ops.resume_text import normalize_text_for_ats
from app.career_ops.tailoring_review import build_tailoring_review_report
from app.schemas.models import ResumeData, TailoredPDFResult


class CareerOpsPDFError(Exception):
    """Raised when tailored PDF generation fails."""


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
    template_name: str | None = None,
) -> TailoredPDFResult:
    """Tailor a structured resume to the JD, render HTML, and return PDF bytes."""
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
        template_name=template_name,
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
    review_report = build_tailoring_review_report(
        original_resume=normalized_resume,
        tailored_resume=tailored_resume,
        job_description=job_description,
        keyword_targets=keyword_targets,
    )
    return TailoredPDFResult(
        filename=filename,
        pdf_bytes=pdf_bytes,
        tailored_resume=tailored_resume,
        keyword_targets=keyword_targets,
        review_report=review_report,
    )


__all__ = [
    "CareerOpsPDFError",
    "generate_tailored_resume_pdf",
    "normalize_text_for_ats",
    "render_resume_html",
]
