from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from app.ai.core.invoke import invoke_text_task
from app.ai.prompts.generate_outreach_message import (
    build_generate_outreach_message_prompt,
)

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = object


class OutreachMessageRunnableInput(BaseModel):
    resume_data: dict[str, Any]
    job_description: str = Field(min_length=1)
    language: str = Field(min_length=1)
    config: LLMConfig | None = None
    max_tokens: int = 1024


def _build_outreach_message_payload(
    task_input: OutreachMessageRunnableInput,
) -> dict[str, object]:
    prompt = build_generate_outreach_message_prompt(
        resume_data=task_input.resume_data,
        job_description=task_input.job_description,
        language=task_input.language,
    )
    return {
        "prompt": prompt,
        "system_prompt": (
            "You are a professional networking coach. "
            "Write genuine, engaging cold outreach messages."
        ),
        "config": task_input.config,
        "max_tokens": task_input.max_tokens,
    }


async def _invoke_outreach_message_payload(payload: dict[str, object]) -> str:
    return await invoke_text_task(
        prompt=payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        config=payload.get("config"),
        max_tokens=payload.get("max_tokens", 1024),
    )


def build_generate_outreach_message_runnable() -> RunnableSerializable[
    OutreachMessageRunnableInput, str
]:
    return RunnableLambda(_build_outreach_message_payload) | RunnableLambda(
        _invoke_outreach_message_payload
    )


async def generate_outreach_message_text(
    *,
    resume_data: dict[str, Any],
    job_description: str,
    language: str = "en",
    config: LLMConfig | None = None,
    max_tokens: int = 1024,
) -> str:
    task_input = OutreachMessageRunnableInput(
        resume_data=resume_data,
        job_description=job_description,
        language=language,
        config=config,
        max_tokens=max_tokens,
    )
    result = await build_generate_outreach_message_runnable().ainvoke(task_input)
    return result.strip()
