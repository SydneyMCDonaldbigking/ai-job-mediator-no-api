import json

from langchain_core.prompts import PromptTemplate

from app.schemas.models import ResumeData

SEARCH_QUERY_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """
You generate job search keywords for a candidate resume.

Return JSON only with this shape:
{{
  "candidate_profile_summary": "short summary",
  "keywords": ["keyword 1", "keyword 2"],
  "location": {location_example}
}}

Rules:
- Output 2 to 5 search keywords.
- Keep the keywords in {language}.
- Make them realistic job search phrases.
- Do not invent experience that is unsupported by the resume.
- Keep location as a plain string.

Resume summary:
{summary}

Recent titles:
{titles}

Skills:
{skills}
""".strip()
)


def build_search_query_prompt(
    *, resume: ResumeData, language: str, default_location: str
) -> str:
    summary = resume.summary or "No summary provided."
    skills = (
        ", ".join(resume.additional.technicalSkills[:12])
        or "No technical skills listed."
    )
    titles = (
        ", ".join(entry.title for entry in resume.workExperience[:5] if entry.title)
        or "No recent titles listed."
    )
    location_example = json.dumps(default_location)

    return SEARCH_QUERY_PROMPT_TEMPLATE.format(
        language=language,
        location_example=location_example,
        summary=summary,
        titles=titles,
        skills=skills,
    )
