from langchain_core.prompts import PromptTemplate

from app.prompts import get_language_name
from app.prompts.templates import GENERATE_TITLE_PROMPT


GENERATE_RESUME_TITLE_PROMPT_TEMPLATE = PromptTemplate.from_template(
    GENERATE_TITLE_PROMPT.strip()
)


def build_generate_resume_title_prompt(
    *,
    job_description: str,
    language: str,
) -> str:
    return GENERATE_RESUME_TITLE_PROMPT_TEMPLATE.format(
        job_description=job_description,
        output_language=get_language_name(language),
    )
