from langchain_core.prompts import PromptTemplate

from app.prompts.templates import PARSE_RESUME_PROMPT, RESUME_SCHEMA


PARSE_RESUME_PROMPT_TEMPLATE = PromptTemplate.from_template(PARSE_RESUME_PROMPT.strip())


def build_parse_resume_prompt(*, resume_text: str) -> str:
    return PARSE_RESUME_PROMPT_TEMPLATE.format(
        schema=RESUME_SCHEMA,
        resume_text=resume_text.strip(),
    )
