import json

from langchain_core.prompts import PromptTemplate

from app.prompts import get_language_name
from app.prompts.templates import COVER_LETTER_PROMPT


GENERATE_COVER_LETTER_PROMPT_TEMPLATE = PromptTemplate.from_template(
    COVER_LETTER_PROMPT.strip()
)


def build_generate_cover_letter_prompt(
    *,
    resume_data: dict,
    job_description: str,
    language: str,
) -> str:
    return GENERATE_COVER_LETTER_PROMPT_TEMPLATE.format(
        job_description=job_description,
        resume_data=json.dumps(resume_data, ensure_ascii=False),
        output_language=get_language_name(language),
    )
