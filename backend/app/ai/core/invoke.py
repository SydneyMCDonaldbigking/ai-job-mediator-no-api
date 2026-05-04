from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langchain_core.runnables import RunnableLambda, RunnableSerializable

if TYPE_CHECKING:
    from app.llm import LLMConfig
else:
    LLMConfig = Any


async def _invoke_litellm_json(payload: dict[str, Any]) -> dict[str, Any]:
    from app.llm import complete_json

    return await complete_json(
        payload["prompt"],
        system_prompt=payload.get("system_prompt"),
        config=payload.get("config"),
        max_tokens=payload.get("max_tokens", 4096),
        retries=payload.get("retries", 2),
    )


def build_litellm_json_runnable() -> RunnableSerializable[dict[str, Any], dict[str, Any]]:
    """Return a minimal LangChain runnable backed by the existing LiteLLM gateway."""

    return RunnableLambda(_invoke_litellm_json)


async def invoke_json_task(
    prompt: str,
    system_prompt: str | None = None,
    config: LLMConfig | None = None,
    max_tokens: int = 4096,
    retries: int = 2,
) -> dict[str, Any]:
    """Invoke an AI task that expects a JSON object response."""
    runnable = build_litellm_json_runnable()
    return await runnable.ainvoke(
        {
            "prompt": prompt,
            "system_prompt": system_prompt,
            "config": config,
            "max_tokens": max_tokens,
            "retries": retries,
        }
    )


async def invoke_text_task(
    prompt: str,
    system_prompt: str | None = None,
    config: LLMConfig | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    from app.llm import complete

    return await complete(
        prompt=prompt,
        system_prompt=system_prompt,
        config=config,
        max_tokens=max_tokens,
        temperature=temperature,
    )
