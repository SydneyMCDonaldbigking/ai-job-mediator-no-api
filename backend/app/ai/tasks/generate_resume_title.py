from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from app.ai.core.invoke import invoke_text_task
from app.ai.prompts.generate_resume_title import (
    build_generate_resume_title_prompt,
)

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = object


class ResumeTitleRunnableInput(BaseModel):
    job_description: str = Field(min_length=1)
    language: str = Field(min_length=1)
    config: LLMConfig | None = None
    max_tokens: int = 60
    temperature: float = 0.3


def normalize_generated_resume_title(title: str) -> str:
    return title.strip()


def _build_resume_title_payload(
    task_input: ResumeTitleRunnableInput,
) -> dict[str, object]:
    prompt = build_generate_resume_title_prompt(
        job_description=task_input.job_description,
        language=task_input.language,
    )
    return {
        "prompt": prompt,
        "system_prompt": "You extract job titles and company names from job descriptions.",
        "config": task_input.config,
        "max_tokens": task_input.max_tokens,
        "temperature": task_input.temperature,
    }


async def _invoke_resume_title_payload(payload: dict[str, object]) -> str:
    return await invoke_text_task(
        prompt=payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        config=payload.get("config"),
        max_tokens=payload.get("max_tokens", 60),
        temperature=payload.get("temperature", 0.3),
    )


def build_generate_resume_title_runnable() -> RunnableSerializable[
    ResumeTitleRunnableInput, str
]:
    return RunnableLambda(_build_resume_title_payload) | RunnableLambda(
        _invoke_resume_title_payload
    )


async def generate_resume_title_text(
    *,
    job_description: str,
    language: str = "en",
    config: LLMConfig | None = None,
    max_tokens: int = 60,
    temperature: float = 0.3,
) -> str:
    task_input = ResumeTitleRunnableInput(
        job_description=job_description,
        language=language,
        config=config,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    result = await build_generate_resume_title_runnable().ainvoke(task_input)
    return normalize_generated_resume_title(result)
