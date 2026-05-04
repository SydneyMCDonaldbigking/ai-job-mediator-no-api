from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from app.ai.core.invoke import invoke_json_task as core_invoke_json_task
from app.ai.parsers.parse_resume import normalize_resume_task_result
from app.ai.prompts.parse_resume import build_parse_resume_prompt
from app.schemas.models import ResumeData

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = object


class ParseResumeRunnableInput(BaseModel):
    resume_text: str = Field(min_length=1)
    config: LLMConfig | None = None
    max_tokens: int = 4096
    retries: int = 2


def _build_parse_resume_payload(task_input: ParseResumeRunnableInput) -> dict[str, object]:
    prompt = build_parse_resume_prompt(resume_text=task_input.resume_text)
    return {
        "prompt": prompt,
        "system_prompt": None,
        "config": task_input.config,
        "max_tokens": task_input.max_tokens,
        "retries": task_input.retries,
    }


async def invoke_json_task(
    prompt: str,
    system_prompt: str | None = None,
    config: LLMConfig | None = None,
    max_tokens: int = 4096,
    retries: int = 2,
) -> dict[str, object]:
    return await core_invoke_json_task(
        prompt,
        system_prompt=system_prompt,
        config=config,
        max_tokens=max_tokens,
        retries=retries,
    )


async def _invoke_parse_resume_payload(payload: dict[str, object]) -> dict[str, object]:
    return await invoke_json_task(
        payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        config=payload.get("config"),
        max_tokens=payload.get("max_tokens", 4096),
        retries=payload.get("retries", 2),
    )


def build_parse_resume_runnable() -> RunnableSerializable[
    ParseResumeRunnableInput, dict[str, object]
]:
    return RunnableLambda(_build_parse_resume_payload) | RunnableLambda(
        _invoke_parse_resume_payload
    )


async def generate_parsed_resume(
    *,
    resume_text: str,
    config: LLMConfig | None = None,
    max_tokens: int = 4096,
    retries: int = 2,
) -> ResumeData:
    task_input = ParseResumeRunnableInput(
        resume_text=resume_text,
        config=config,
        max_tokens=max_tokens,
        retries=retries,
    )
    raw_result = await build_parse_resume_runnable().ainvoke(task_input)
    parsed_result = ResumeData.model_validate(raw_result)
    return normalize_resume_task_result(parsed_result)
