"""Career Ops helpers for job evaluation and ATS PDF generation."""

from app.career_ops.evaluator import (
    DEFAULT_DIMENSION_BLUEPRINT,
    build_job_evaluation_prompt,
    coerce_resume_data,
    evaluate_job_fit,
    extract_keyword_targets,
    resume_to_text,
    summarize_af_scores,
)
from app.career_ops.market_data import (
    build_market_search_queries,
    extract_salary_mentions,
    fetch_market_signals,
    parse_duckduckgo_results,
)
from app.career_ops.pdf_generator import (
    generate_tailored_resume_pdf,
    normalize_text_for_ats,
    render_resume_html,
)
from app.career_ops.scanner import (
    build_title_filter,
    detect_api,
    ensure_portals_config,
    load_portals_config,
    save_portals_config,
    scan_portals,
)

__all__ = [
    "DEFAULT_DIMENSION_BLUEPRINT",
    "build_job_evaluation_prompt",
    "coerce_resume_data",
    "evaluate_job_fit",
    "extract_keyword_targets",
    "resume_to_text",
    "summarize_af_scores",
    "build_market_search_queries",
    "extract_salary_mentions",
    "fetch_market_signals",
    "parse_duckduckgo_results",
    "generate_tailored_resume_pdf",
    "normalize_text_for_ats",
    "render_resume_html",
    "build_title_filter",
    "detect_api",
    "ensure_portals_config",
    "load_portals_config",
    "save_portals_config",
    "scan_portals",
]
