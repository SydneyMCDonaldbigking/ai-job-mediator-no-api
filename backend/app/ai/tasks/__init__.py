"""Task entrypoints for AI workflows."""

from app.ai.tasks.evaluate_job import (
    GeneratedJobEvaluation,
    generate_job_evaluation,
)
from app.ai.tasks.generate_cover_letter import generate_cover_letter_text
from app.ai.tasks.generate_outreach_message import (
    generate_outreach_message_text,
)
from app.ai.tasks.generate_resume_title import generate_resume_title_text
from app.ai.tasks.parse_resume import generate_parsed_resume
from app.ai.tasks.generate_search_queries import (
    GeneratedSearchQueries,
    generate_search_queries,
    to_seek_search_plan,
)

__all__ = [
    "GeneratedJobEvaluation",
    "GeneratedSearchQueries",
    "generate_cover_letter_text",
    "generate_job_evaluation",
    "generate_outreach_message_text",
    "generate_parsed_resume",
    "generate_resume_title_text",
    "generate_search_queries",
    "to_seek_search_plan",
]
