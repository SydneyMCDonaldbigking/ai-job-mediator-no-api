from __future__ import annotations

from typing import TYPE_CHECKING

from langchain_core.runnables import RunnableLambda, RunnableSerializable
from pydantic import BaseModel, Field

from app.ai.core.invoke import invoke_json_task as core_invoke_json_task
from app.ai.parsers.evaluate_job import (
    EvaluationDimensionResult,
    EvaluationTaskResult,
    normalize_evaluation_task_result,
)
from app.ai.prompts.evaluate_job import build_evaluate_job_prompt

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = object

DEFAULT_EVALUATION_SYSTEM_PROMPT = (
    "You are a truthful job-search strategist. "
    "Never invent compensation facts or experience not present in the resume."
)


class GeneratedJobEvaluation(BaseModel):
    executive_summary: str = Field(min_length=1)
    archetype: str = Field(min_length=1)
    overall_label: str = Field(min_length=1)
    dimensions: list[EvaluationDimensionResult] = Field(min_length=1)
    tailoring_priorities: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    keyword_targets: list[str] = Field(default_factory=list)


class EvaluateJobRunnableInput(BaseModel):
    resume_text: str = Field(min_length=1)
    job_description: str = Field(min_length=1)
    keyword_targets: list[str] = Field(default_factory=list)
    market_context: str = ""
    config: LLMConfig | None = None
    max_tokens: int = 2400
    retries: int = 2


def _build_evaluate_job_payload(
    task_input: EvaluateJobRunnableInput,
) -> dict[str, object]:
    prompt = build_evaluate_job_prompt(
        resume_text=task_input.resume_text,
        job_description=task_input.job_description,
        keyword_targets=task_input.keyword_targets,
        market_context=task_input.market_context,
    )
    return {
        "prompt": prompt,
        "system_prompt": DEFAULT_EVALUATION_SYSTEM_PROMPT,
        "config": task_input.config,
        "max_tokens": task_input.max_tokens,
        "retries": task_input.retries,
    }


async def invoke_json_task(
    prompt: str,
    system_prompt: str | None = None,
    config: LLMConfig | None = None,
    max_tokens: int = 2400,
    retries: int = 2,
) -> dict[str, object]:
    return await core_invoke_json_task(
        prompt,
        system_prompt=system_prompt,
        config=config,
        max_tokens=max_tokens,
        retries=retries,
    )


async def _invoke_evaluate_job_payload(payload: dict[str, object]) -> dict[str, object]:
    return await invoke_json_task(
        payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        config=payload.get("config"),
        max_tokens=payload.get("max_tokens", 2400),
        retries=payload.get("retries", 2),
    )


def build_evaluate_job_runnable() -> RunnableSerializable[
    EvaluateJobRunnableInput, dict[str, object]
]:
    return RunnableLambda(_build_evaluate_job_payload) | RunnableLambda(
        _invoke_evaluate_job_payload
    )


async def generate_job_evaluation(
    *,
    resume_text: str,
    job_description: str,
    keyword_targets: list[str],
    market_context: str,
    config: LLMConfig | None = None,
    max_tokens: int = 2400,
    retries: int = 2,
) -> GeneratedJobEvaluation:
    task_input = EvaluateJobRunnableInput(
        resume_text=resume_text,
        job_description=job_description,
        keyword_targets=keyword_targets,
        market_context=market_context,
        config=config,
        max_tokens=max_tokens,
        retries=retries,
    )
    runnable = build_evaluate_job_runnable()
    raw_result = await runnable.ainvoke(task_input)
    parsed_result = EvaluationTaskResult.model_validate(raw_result)
    normalized_result = normalize_evaluation_task_result(parsed_result)
    return GeneratedJobEvaluation(**normalized_result.model_dump())
