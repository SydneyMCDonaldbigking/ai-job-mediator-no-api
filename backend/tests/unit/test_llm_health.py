"""Unit tests for LLM health check behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.llm import (
    LLMConfig,
    _normalize_api_base,
    build_llm_config_chain,
    check_llm_health,
    complete,
    complete_json,
    get_llm_config,
    is_fallback_eligible_error,
)


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

    def test_build_llm_config_chain_uses_legacy_single_provider_when_chain_missing(self):
        stored = {
            "provider": "openrouter",
            "model": "openai/gpt-oss-20b:free",
            "api_base": None,
            "api_keys": {"openrouter": "or-key"},
        }

        configs = build_llm_config_chain(stored)

        assert [config.provider for config in configs] == ["openrouter"]
        assert [config.model for config in configs] == ["openai/gpt-oss-20b:free"]
        assert configs[0].api_key == "or-key"

    def test_build_llm_config_chain_uses_ordered_chain_when_present(self):
        stored = {
            "provider": "openrouter",
            "model": "openai/gpt-oss-20b:free",
            "api_keys": {
                "openrouter": "or-key",
                "openai": "nv-key",
            },
            "llm_fallback_chain": [
                {
                    "name": "openrouter-free",
                    "provider": "openrouter",
                    "model": "openai/gpt-oss-20b:free",
                    "api_key_provider": "openrouter",
                    "api_base": None,
                    "enabled": True,
                },
                {
                    "name": "nvidia-free",
                    "provider": "openai",
                    "model": "meta/llama-3.1-70b-instruct",
                    "api_key_provider": "openai",
                    "api_base": "https://integrate.api.nvidia.com/v1",
                    "enabled": True,
                },
                {
                    "name": "openrouter-auto",
                    "provider": "openrouter",
                    "model": "auto",
                    "api_key_provider": "openrouter",
                    "api_base": None,
                    "enabled": True,
                },
            ],
        }

        configs = build_llm_config_chain(stored)

        assert [(config.provider, config.model) for config in configs] == [
            ("openrouter", "openai/gpt-oss-20b:free"),
            ("openai", "meta/llama-3.1-70b-instruct"),
            ("openrouter", "auto"),
        ]
        assert [config.api_key for config in configs] == ["or-key", "nv-key", "or-key"]
        assert configs[1].api_base == "https://integrate.api.nvidia.com/v1"

    def test_build_llm_config_chain_skips_disabled_entries(self):
        stored = {
            "api_keys": {"openrouter": "or-key", "openai": "nv-key"},
            "llm_fallback_chain": [
                {
                    "name": "disabled-openrouter-free",
                    "provider": "openrouter",
                    "model": "openai/gpt-oss-20b:free",
                    "api_key_provider": "openrouter",
                    "api_base": None,
                    "enabled": False,
                },
                {
                    "name": "nvidia-free",
                    "provider": "openai",
                    "model": "meta/llama-3.1-70b-instruct",
                    "api_key_provider": "openai",
                    "api_base": "https://integrate.api.nvidia.com/v1",
                    "enabled": True,
                },
            ],
        }

        configs = build_llm_config_chain(stored)

        assert [(config.provider, config.model) for config in configs] == [
            ("openai", "meta/llama-3.1-70b-instruct"),
        ]

    def test_fallback_eligible_error_matches_provider_access_failures(self):
        assert is_fallback_eligible_error(RuntimeError("403 Forbidden")) is True
        assert is_fallback_eligible_error(RuntimeError("429 rate limit exceeded")) is True
        assert is_fallback_eligible_error(RuntimeError("insufficient credits")) is True

    def test_fallback_eligible_error_rejects_application_bugs(self):
        assert is_fallback_eligible_error(ValueError("invalid json payload")) is False
        assert is_fallback_eligible_error(RuntimeError("field required")) is False

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

    @pytest.mark.asyncio
    @patch("app.llm.litellm.acompletion", new_callable=AsyncMock)
    async def test_check_llm_health_falls_from_openrouter_free_to_nvidia(
        self,
        mock_acompletion,
    ):
        configs = [
            LLMConfig(provider="openrouter", model="openai/gpt-oss-20b:free", api_key="or-key"),
            LLMConfig(
                provider="openai",
                model="meta/llama-3.1-70b-instruct",
                api_key="nv-key",
                api_base="https://integrate.api.nvidia.com/v1",
            ),
        ]

        mock_acompletion.side_effect = [
            RuntimeError("403 Forbidden"),
            _response_with_content("hello"),
        ]

        result = await check_llm_health(configs[0], fallback_chain=configs)

        assert result["healthy"] is True
        assert result["provider"] == "openai"
        assert result["model"] == "meta/llama-3.1-70b-instruct"
        assert mock_acompletion.await_count == 2

    @pytest.mark.asyncio
    @patch("app.llm.litellm.acompletion", new_callable=AsyncMock)
    async def test_check_llm_health_falls_to_openrouter_auto_after_nvidia_failure(
        self,
        mock_acompletion,
    ):
        configs = [
            LLMConfig(provider="openrouter", model="openai/gpt-oss-20b:free", api_key="or-key"),
            LLMConfig(
                provider="openai",
                model="meta/llama-3.1-70b-instruct",
                api_key="nv-key",
                api_base="https://integrate.api.nvidia.com/v1",
            ),
            LLMConfig(provider="openrouter", model="auto", api_key="or-key"),
        ]

        mock_acompletion.side_effect = [
            RuntimeError("403 Forbidden"),
            RuntimeError("429 rate limit exceeded"),
            _response_with_content("hello"),
        ]

        result = await check_llm_health(configs[0], fallback_chain=configs)

        assert result["healthy"] is True
        assert result["provider"] == "openrouter"
        assert result["model"] == "auto"
        assert mock_acompletion.await_count == 3

    @pytest.mark.asyncio
    @patch("app.llm.litellm.acompletion", new_callable=AsyncMock)
    async def test_check_llm_health_stops_on_non_fallback_error(
        self,
        mock_acompletion,
    ):
        configs = [
            LLMConfig(provider="openrouter", model="openai/gpt-oss-20b:free", api_key="or-key"),
            LLMConfig(
                provider="openai",
                model="meta/llama-3.1-70b-instruct",
                api_key="nv-key",
                api_base="https://integrate.api.nvidia.com/v1",
            ),
        ]

        mock_acompletion.side_effect = RuntimeError("invalid json payload")

        result = await check_llm_health(configs[0], fallback_chain=configs)

        assert result["healthy"] is False
        assert result["provider"] == "openrouter"
        assert mock_acompletion.await_count == 1

    @patch("app.llm._load_stored_config")
    def test_get_llm_config_returns_first_enabled_chain_entry(self, mock_load):
        mock_load.return_value = {
            "api_keys": {"openrouter": "or-key", "openai": "nv-key"},
            "llm_fallback_chain": [
                {
                    "name": "openrouter-free",
                    "provider": "openrouter",
                    "model": "openai/gpt-oss-20b:free",
                    "api_key_provider": "openrouter",
                    "api_base": None,
                    "enabled": True,
                },
                {
                    "name": "nvidia-free",
                    "provider": "openai",
                    "model": "meta/llama-3.1-70b-instruct",
                    "api_key_provider": "openai",
                    "api_base": "https://integrate.api.nvidia.com/v1",
                    "enabled": True,
                },
            ],
        }

        config = get_llm_config()

        assert config.provider == "openrouter"
        assert config.model == "openai/gpt-oss-20b:free"
        assert config.api_key == "or-key"

    @pytest.mark.asyncio
    @patch("app.llm.get_router")
    async def test_complete_falls_through_full_provider_chain(self, mock_get_router):
        openrouter_free = LLMConfig(
            provider="openrouter",
            model="openai/gpt-oss-20b:free",
            api_key="or-key",
        )
        nvidia_free = LLMConfig(
            provider="openai",
            model="meta/llama-3.1-70b-instruct",
            api_key="nv-key",
            api_base="https://integrate.api.nvidia.com/v1",
        )
        openrouter_auto = LLMConfig(
            provider="openrouter",
            model="auto",
            api_key="or-key",
        )

        free_router = SimpleNamespace(acompletion=AsyncMock(side_effect=RuntimeError("403 Forbidden")))
        nvidia_router = SimpleNamespace(acompletion=AsyncMock(side_effect=RuntimeError("429 rate limit exceeded")))
        auto_router = SimpleNamespace(acompletion=AsyncMock(return_value=_response_with_content("final answer")))

        def fake_get_router(config=None):
            if config.provider == "openrouter" and config.model == "openai/gpt-oss-20b:free":
                return free_router, config
            if config.provider == "openai":
                return nvidia_router, config
            if config.provider == "openrouter" and config.model == "auto":
                return auto_router, config
            raise AssertionError(f"Unexpected config: {config}")

        mock_get_router.side_effect = fake_get_router

        with patch("app.llm._load_stored_config", return_value={
            "api_keys": {"openrouter": "or-key", "openai": "nv-key"},
            "llm_fallback_chain": [
                {
                    "name": "openrouter-free",
                    "provider": "openrouter",
                    "model": "openai/gpt-oss-20b:free",
                    "api_key_provider": "openrouter",
                    "api_base": None,
                    "enabled": True,
                },
                {
                    "name": "nvidia-free",
                    "provider": "openai",
                    "model": "meta/llama-3.1-70b-instruct",
                    "api_key_provider": "openai",
                    "api_base": "https://integrate.api.nvidia.com/v1",
                    "enabled": True,
                },
                {
                    "name": "openrouter-auto",
                    "provider": "openrouter",
                    "model": "auto",
                    "api_key_provider": "openrouter",
                    "api_base": None,
                    "enabled": True,
                },
            ],
        }):
            result = await complete("hello")

        assert result == "final answer"

    @pytest.mark.asyncio
    @patch("app.llm._supports_json_mode", return_value=False)
    @patch("app.llm.get_router")
    async def test_complete_json_falls_through_full_provider_chain(
        self,
        mock_get_router,
        _mock_supports_json_mode,
    ):
        free_router = SimpleNamespace(acompletion=AsyncMock(side_effect=RuntimeError("403 Forbidden")))
        nvidia_router = SimpleNamespace(acompletion=AsyncMock(side_effect=RuntimeError("429 rate limit exceeded")))
        auto_router = SimpleNamespace(
            acompletion=AsyncMock(return_value=_response_with_content('{"status":"ok"}'))
        )

        def fake_get_router(config=None):
            if config.provider == "openrouter" and config.model == "openai/gpt-oss-20b:free":
                return free_router, config
            if config.provider == "openai":
                return nvidia_router, config
            if config.provider == "openrouter" and config.model == "auto":
                return auto_router, config
            raise AssertionError(f"Unexpected config: {config}")

        mock_get_router.side_effect = fake_get_router

        with patch("app.llm._load_stored_config", return_value={
            "api_keys": {"openrouter": "or-key", "openai": "nv-key"},
            "llm_fallback_chain": [
                {
                    "name": "openrouter-free",
                    "provider": "openrouter",
                    "model": "openai/gpt-oss-20b:free",
                    "api_key_provider": "openrouter",
                    "api_base": None,
                    "enabled": True,
                },
                {
                    "name": "nvidia-free",
                    "provider": "openai",
                    "model": "meta/llama-3.1-70b-instruct",
                    "api_key_provider": "openai",
                    "api_base": "https://integrate.api.nvidia.com/v1",
                    "enabled": True,
                },
                {
                    "name": "openrouter-auto",
                    "provider": "openrouter",
                    "model": "auto",
                    "api_key_provider": "openrouter",
                    "api_base": None,
                    "enabled": True,
                },
            ],
        }):
            result = await complete_json("hello")

        assert result == {"status": "ok"}
