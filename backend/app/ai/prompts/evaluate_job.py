from __future__ import annotations

import json
from typing import Any

from langchain_core.prompts import PromptTemplate

from app.career_ops.evaluator import DEFAULT_DIMENSION_BLUEPRINT

EVALUATE_JOB_PROMPT_TEMPLATE = PromptTemplate.from_template(
    """
You are evaluating a job application using a structured A-F job search framework.

Return JSON only with this shape:
{{
  "executive_summary": "short paragraph",
  "archetype": "short archetype label",
  "overall_label": "weak fit | mixed fit | strong fit",
  "dimensions": [
    {{
      "key": "archetype_fit",
      "category": "A",
      "label": "Archetype Fit",
      "score": 0.0,
      "rationale": "why",
      "evidence": ["resume proof point 1"],
      "risks": ["risk or gap"]
    }}
  ],
  "tailoring_priorities": ["priority 1"],
  "interview_focus": ["story 1"],
  "keyword_targets": ["keyword 1"]
}}

Use exactly these dimension definitions:
{dimension_lines}

Resume:
{resume_text}

Job Description:
{job_description}

Keyword Targets:
{keyword_targets}

Market Context:
{market_context}
""".strip()
)


def _format_dimension_lines(
    dimension_blueprint: list[dict[str, str]] | None = None,
) -> str:
    blueprint = dimension_blueprint or DEFAULT_DIMENSION_BLUEPRINT
    return "\n".join(
        (
            f"- {item['category']}::{item['key']} - "
            f"{item['label']}: {item['prompt_focus']}"
        )
        for item in blueprint
    )


def build_evaluate_job_prompt(
    *,
    resume_text: str,
    job_description: str,
    keyword_targets: list[str],
    market_context: str,
    dimension_blueprint: list[dict[str, str]] | None = None,
) -> str:
    return EVALUATE_JOB_PROMPT_TEMPLATE.format(
        dimension_lines=_format_dimension_lines(dimension_blueprint),
        resume_text=resume_text.strip(),
        job_description=job_description.strip(),
        keyword_targets=json.dumps(keyword_targets, ensure_ascii=False),
        market_context=market_context.strip(),
    )
