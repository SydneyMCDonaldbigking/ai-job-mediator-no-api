from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from app.ai.core.invoke import invoke_text_task
from app.ai.prompts.generate_cover_letter import build_generate_cover_letter_prompt

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = object


class CoverLetterRunnableInput(BaseModel):
    resume_data: dict[str, Any]
    job_description: str = Field(min_length=1)
    language: str = Field(min_length=1)
    config: LLMConfig | None = None
    max_tokens: int = 2048


def _build_cover_letter_payload(
    task_input: CoverLetterRunnableInput,
) -> dict[str, object]:
    prompt = build_generate_cover_letter_prompt(
        resume_data=task_input.resume_data,
        job_description=task_input.job_description,
        language=task_input.language,
    )
    return {
        "prompt": prompt,
        "system_prompt": (
            "You are a professional career coach and resume writer. "
            "Write compelling, personalized cover letters."
        ),
        "config": task_input.config,
        "max_tokens": task_input.max_tokens,
    }


async def _invoke_cover_letter_payload(payload: dict[str, object]) -> str:
    return await invoke_text_task(
        prompt=payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        config=payload.get("config"),
        max_tokens=payload.get("max_tokens", 2048),
    )


def build_generate_cover_letter_runnable() -> RunnableSerializable[
    CoverLetterRunnableInput, str
]:
    return RunnableLambda(_build_cover_letter_payload) | RunnableLambda(
        _invoke_cover_letter_payload
    )


async def generate_cover_letter_text(
    *,
    resume_data: dict[str, Any],
    job_description: str,
    language: str = "en",
    config: LLMConfig | None = None,
    max_tokens: int = 2048,
) -> str:
    task_input = CoverLetterRunnableInput(
        resume_data=resume_data,
        job_description=job_description,
        language=language,
        config=config,
        max_tokens=max_tokens,
    )
    result = await build_generate_cover_letter_runnable().ainvoke(task_input)
    return result.strip()
