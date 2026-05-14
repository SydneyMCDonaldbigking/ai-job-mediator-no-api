# LLM Fallback Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a config-driven backend LLM fallback chain that tries OpenRouter free, then NVIDIA free, then OpenRouter `auto`.

**Architecture:** Keep the existing single-provider config working, but add a new `llm_fallback_chain` list in `backend/data/config.json`. Parse that list into ordered `LLMConfig` candidates inside the backend, then update runtime LLM execution to try candidates sequentially only for fallback-eligible provider errors.

**Tech Stack:** Python 3.13, FastAPI, Pydantic, LiteLLM, pytest, unittest.mock

---

## File Structure

- Modify: `backend/app/llm.py`
  - Add typed chain parsing helpers
  - Add fallback eligibility logic
  - Add sequential execution across multiple `LLMConfig` candidates
- Modify: `backend/app/schemas/models.py`
  - Add config models for fallback chain entries if they are needed by config endpoints/tests
- Modify: `backend/app/routers/config.py`
  - Preserve current config behavior
  - Optionally include `llm_fallback_chain` passthrough when loading/saving config
- Test: `backend/tests/unit/test_llm_health.py`
  - Add parsing tests and fallback execution tests

### Task 1: Parse Chain Config With Backward Compatibility

**Files:**
- Modify: `backend/app/llm.py`
- Test: `backend/tests/unit/test_llm_health.py`

- [ ] **Step 1: Write the failing parsing tests**

Add these tests to `backend/tests/unit/test_llm_health.py`:

```python
def test_get_llm_configs_uses_legacy_single_provider_when_chain_missing():
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


def test_get_llm_configs_uses_ordered_chain_when_present():
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


def test_get_llm_configs_skips_disabled_entries():
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py -k "build_llm_config_chain" -v
```

Expected: FAIL because `build_llm_config_chain` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add a minimal parser in `backend/app/llm.py` near `get_llm_config()`:

```python
def build_llm_config_chain(stored: dict[str, Any] | None = None) -> list[LLMConfig]:
    stored = stored or _load_stored_config()
    entries = stored.get("llm_fallback_chain") or []
    api_keys = stored.get("api_keys", {})
    configs: list[LLMConfig] = []

    if isinstance(entries, list):
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if entry.get("enabled", True) is False:
                continue
            provider = str(entry.get("provider") or "").strip()
            model = str(entry.get("model") or "").strip()
            key_provider = str(entry.get("api_key_provider") or provider).strip()
            if not provider or not model:
                continue
            api_key = api_keys.get(_PROVIDER_KEY_MAP.get(key_provider, key_provider), "")
            configs.append(
                LLMConfig(
                    provider=provider,
                    model=model,
                    api_key=api_key,
                    api_base=entry.get("api_base"),
                )
            )

    if configs:
        return configs

    provider = stored.get("provider", settings.llm_provider)
    return [
        LLMConfig(
            provider=provider,
            model=stored.get("model", settings.llm_model),
            api_key=resolve_api_key(stored, provider),
            api_base=stored.get("api_base", settings.llm_api_base),
        )
    ]
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py -k "build_llm_config_chain" -v
```

Expected: PASS for the three new parsing tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm.py backend/tests/unit/test_llm_health.py
git commit -m "feat: parse config-driven llm fallback chain"
```

### Task 2: Add Fallback Eligibility Rules

**Files:**
- Modify: `backend/app/llm.py`
- Test: `backend/tests/unit/test_llm_health.py`

- [ ] **Step 1: Write the failing fallback classification tests**

Add these tests:

```python
def test_fallback_eligible_error_matches_provider_access_failures():
    assert is_fallback_eligible_error(RuntimeError("403 Forbidden")) is True
    assert is_fallback_eligible_error(RuntimeError("429 rate limit exceeded")) is True
    assert is_fallback_eligible_error(RuntimeError("insufficient credits")) is True


def test_fallback_eligible_error_rejects_application_bugs():
    assert is_fallback_eligible_error(ValueError("invalid json payload")) is False
    assert is_fallback_eligible_error(RuntimeError("field required")) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py -k "fallback_eligible_error" -v
```

Expected: FAIL because `is_fallback_eligible_error` does not exist yet.

- [ ] **Step 3: Write minimal implementation**

Add this helper in `backend/app/llm.py`:

```python
def is_fallback_eligible_error(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = (
        "401",
        "403",
        "429",
        "quota",
        "credit",
        "credits",
        "insufficient",
        "forbidden",
        "rate limit",
        "free",
    )
    return any(marker in message for marker in markers)
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py -k "fallback_eligible_error" -v
```

Expected: PASS for the new eligibility tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm.py backend/tests/unit/test_llm_health.py
git commit -m "feat: classify llm fallback eligible errors"
```

### Task 3: Execute Sequential Fallback Across Providers

**Files:**
- Modify: `backend/app/llm.py`
- Test: `backend/tests/unit/test_llm_health.py`

- [ ] **Step 1: Write the failing sequential fallback tests**

Add these tests:

```python
@pytest.mark.asyncio
@patch("app.llm.litellm.acompletion", new_callable=AsyncMock)
async def test_check_llm_health_falls_from_openrouter_free_to_nvidia(mock_acompletion):
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
async def test_check_llm_health_falls_to_openrouter_auto_after_nvidia_failure(mock_acompletion):
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
async def test_check_llm_health_stops_on_non_fallback_error(mock_acompletion):
    configs = [
        LLMConfig(provider="openrouter", model="openai/gpt-oss-20b:free", api_key="or-key"),
        LLMConfig(provider="openai", model="meta/llama-3.1-70b-instruct", api_key="nv-key"),
    ]

    mock_acompletion.side_effect = RuntimeError("invalid json payload")

    result = await check_llm_health(configs[0], fallback_chain=configs)

    assert result["healthy"] is False
    assert result["provider"] == "openrouter"
    assert mock_acompletion.await_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py -k "falls_from_openrouter_free_to_nvidia or falls_to_openrouter_auto or stops_on_non_fallback_error" -v
```

Expected: FAIL because `check_llm_health()` does not accept `fallback_chain` yet.

- [ ] **Step 3: Write minimal implementation**

Update `check_llm_health()` in `backend/app/llm.py`:

```python
async def check_llm_health(
    config: LLMConfig | None = None,
    *,
    include_details: bool = False,
    test_prompt: str | None = None,
    fallback_chain: list[LLMConfig] | None = None,
) -> dict[str, Any]:
    if config is None:
        config = get_llm_config()

    candidates = fallback_chain or [config]
    last_exception: Exception | None = None

    for candidate in candidates:
        try:
            return await _check_llm_health_once(
                candidate,
                include_details=include_details,
                test_prompt=test_prompt,
            )
        except Exception as exc:
            last_exception = exc
            if not is_fallback_eligible_error(exc):
                break

    failed_config = candidates[-1] if candidates else config
    return {
        "healthy": False,
        "provider": failed_config.provider,
        "model": failed_config.model,
        "error_code": "health_check_failed",
        "message": str(last_exception) if last_exception else "unknown llm failure",
    }
```

Also extract the current single-attempt logic into `_check_llm_health_once()` so it can be reused cleanly.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py -v
```

Expected: PASS for all existing and new `test_llm_health.py` tests.

- [ ] **Step 5: Commit**

```bash
git add backend/app/llm.py backend/tests/unit/test_llm_health.py
git commit -m "feat: add sequential llm provider fallback"
```

### Task 4: Wire Runtime Calls To Use The Config Chain

**Files:**
- Modify: `backend/app/llm.py`
- Test: `backend/tests/unit/test_llm_health.py`

- [ ] **Step 1: Write the failing chain selection test**

Add this test:

```python
@patch("app.llm._load_stored_config")
def test_get_llm_config_returns_first_enabled_chain_entry(mock_load):
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py -k "returns_first_enabled_chain_entry" -v
```

Expected: FAIL if `get_llm_config()` still ignores `llm_fallback_chain`.

- [ ] **Step 3: Write minimal implementation**

Update `get_llm_config()`:

```python
def get_llm_config() -> LLMConfig:
    stored = _load_stored_config()
    chain = build_llm_config_chain(stored)
    return chain[0]
```

Keep `build_llm_config_chain()` as the single source of truth for runtime order.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py -v
```

Expected: PASS.

- [ ] **Step 5: Run broader backend verification**

Run:

```bash
.\.venv-ci-debug\Scripts\python -m pytest backend/tests/unit/test_llm_health.py backend/tests/integration/test_health_api.py backend/tests/integration/test_config_api.py -v
```

Expected: PASS with no new failures in config/health behavior.

- [ ] **Step 6: Commit**

```bash
git add backend/app/llm.py backend/tests/unit/test_llm_health.py
git commit -m "feat: wire runtime to config-driven llm chain"
```

