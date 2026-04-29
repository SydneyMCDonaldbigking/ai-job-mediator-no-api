"""Cover letter, outreach message, and resume title generation service."""

from typing import Any

from app.llm import complete
from app.prompts.templates import GENERATE_TITLE_PROMPT
from app.prompts import get_language_name


async def generate_cover_letter_text(**kwargs) -> str:
    from app.ai.tasks.generate_cover_letter import (
        generate_cover_letter_text as task_impl,
    )

    return await task_impl(**kwargs)


async def generate_outreach_message_text(**kwargs) -> str:
    from app.ai.tasks.generate_outreach_message import (
        generate_outreach_message_text as task_impl,
    )

    return await task_impl(**kwargs)


async def generate_cover_letter(
    resume_data: dict[str, Any],
    job_description: str,
    language: str = "en",
) -> str:
    """Generate a cover letter based on resume and job description.

    Args:
        resume_data: Structured resume data (ResumeData format)
        job_description: Target job description text
        language: Output language code (en, es, zh, ja)

    Returns:
        Generated cover letter as plain text
    """
    return await generate_cover_letter_text(
        resume_data=resume_data,
        job_description=job_description,
        language=language,
    )


async def generate_outreach_message(
    resume_data: dict[str, Any],
    job_description: str,
    language: str = "en",
) -> str:
    """Generate a cold outreach message for networking.

    Args:
        resume_data: Structured resume data (ResumeData format)
        job_description: Target job description text
        language: Output language code (en, es, zh, ja)

    Returns:
        Generated outreach message as plain text
    """
    return await generate_outreach_message_text(
        resume_data=resume_data,
        job_description=job_description,
        language=language,
    )


async def generate_resume_title(
    job_description: str,
    language: str = "en",
) -> str:
    """Generate a short descriptive title from a job description.

    Args:
        job_description: Target job description text
        language: Output language code (en, es, zh, ja)

    Returns:
        Generated title like "Senior Frontend Engineer @ Stripe"
    """
    output_language = get_language_name(language)

    prompt = GENERATE_TITLE_PROMPT.format(
        job_description=job_description,
        output_language=output_language,
    )

    result = await complete(
        prompt=prompt,
        system_prompt="You extract job titles and company names from job descriptions.",
        max_tokens=60,
        temperature=0.3,
    )

    # Strip quotes and whitespace, truncate to 80 chars
    title = result.strip().strip("\"'")
    return title[:80]
