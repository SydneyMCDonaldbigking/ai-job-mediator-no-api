"""Unit tests for LLM health check behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.llm import LLMConfig, _normalize_api_base, check_llm_health


def _response_with_content(content: str | None) -> SimpleNamespace:
    """Build a minimal LiteLLM-like response object for health checks."""
    return SimpleNamespace(
        model="gemini-2.5-flash",
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    reasoning_content=None,
                    thinking=None,
                )
            )
        ],
    )


class TestCheckLlmHealth:
    """Tests for provider health probes."""

    def test_openrouter_keeps_v1_api_base(self):
        """OpenRouter requests need the full /api/v1 base URL."""

        assert (
            _normalize_api_base("openrouter", "https://openrouter.ai/api/v1")
            == "https://openrouter.ai/api/v1"
        )

    @pytest.mark.asyncio
    @patch("app.llm.litellm.acompletion", new_callable=AsyncMock)
    async def test_default_health_check_prompt_requests_visible_text_for_gemini(
        self,
        mock_acompletion,
    ):
        """Gemini health checks should use a prompt that produces visible text."""

        async def fake_completion(**kwargs):
            prompt = kwargs["messages"][0]["content"]
            if prompt == "Reply with exactly hello":
                return _response_with_content("hello")
            return _response_with_content(None)

        mock_acompletion.side_effect = fake_completion

        result = await check_llm_health(
            LLMConfig(
                provider="gemini",
                model="gemini-2.5-flash",
                api_key="test-key",
                api_base="https://generativelanguage.googleapis.com/v1beta",
            )
        )

        assert result["healthy"] is True
        assert result["response_model"] == "gemini-2.5-flash"

    @pytest.mark.asyncio
    @patch("app.llm.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.llm.litellm.acompletion", new_callable=AsyncMock)
    async def test_retries_transient_service_unavailable_errors(
        self,
        mock_acompletion,
        mock_sleep,
    ):
        """Transient provider overloads should be retried before failing."""

        mock_acompletion.side_effect = [
            RuntimeError("503 Service Unavailable: model overloaded"),
            _response_with_content("hello"),
        ]

        result = await check_llm_health(
            LLMConfig(
                provider="gemini",
                model="gemini-2.5-flash",
                api_key="test-key",
                api_base="https://generativelanguage.googleapis.com/v1beta",
            )
        )

        assert result["healthy"] is True
        assert mock_acompletion.await_count == 2
        mock_sleep.assert_awaited()
