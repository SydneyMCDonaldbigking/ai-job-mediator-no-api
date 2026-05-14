# LLM Fallback Chain Design

**Goal:** Extend the backend LLM configuration from a single active provider into an ordered provider chain that supports OpenRouter free, NVIDIA free, and OpenRouter auto fallback.

**Scope:** Backend runtime configuration and execution only. The existing frontend settings UI will remain unchanged for this iteration.

## Desired Runtime Order

The backend should attempt LLM calls in this order:

1. OpenRouter free model
2. NVIDIA free model via OpenAI-compatible API
3. OpenRouter `auto`

Fallback should happen only for provider/access/limit style failures, not for ordinary application bugs.

## Configuration Shape

Current `backend/data/config.json` stores one active provider:

```json
{
  "provider": "openrouter",
  "model": "openai/gpt-oss-20b:free",
  "api_base": null,
  "api_keys": {
    "openrouter": "...",
    "openai": "..."
  }
}
```

It will be expanded to support a new ordered chain while preserving backward compatibility:

```json
{
  "provider": "openrouter",
  "model": "openai/gpt-oss-20b:free",
  "api_base": null,
  "api_keys": {
    "openrouter": "...",
    "openai": "..."
  },
  "llm_fallback_chain": [
    {
      "name": "openrouter-free",
      "provider": "openrouter",
      "model": "openai/gpt-oss-20b:free",
      "api_key_provider": "openrouter",
      "api_base": null,
      "enabled": true
    },
    {
      "name": "nvidia-free",
      "provider": "openai",
      "model": "<nvidia-free-model-id>",
      "api_key_provider": "openai",
      "api_base": "https://integrate.api.nvidia.com/v1",
      "enabled": true
    },
    {
      "name": "openrouter-auto",
      "provider": "openrouter",
      "model": "auto",
      "api_key_provider": "openrouter",
      "api_base": null,
      "enabled": true
    }
  ]
}
```

## Backward Compatibility

If `llm_fallback_chain` is missing or empty:

- the backend must keep using the current single-provider config
- existing config endpoints must continue to work
- existing tests for single-provider behavior must still pass

If `llm_fallback_chain` exists:

- runtime calls should use the ordered chain
- current top-level `provider` / `model` still act as legacy defaults and should remain readable

## Runtime Behavior

Add a backend helper that builds an ordered list of candidate `LLMConfig` entries from:

- `llm_fallback_chain` when present
- otherwise the current single resolved config

For each completion request:

1. Try the first enabled candidate
2. If it succeeds, return immediately
3. If it fails with fallback-eligible error, try the next candidate
4. If all candidates fail, return the last meaningful error with fallback trace in logs

## Fallback Eligibility

Fallback should happen only when the error strongly suggests provider-level denial or exhaustion, such as:

- HTTP 401
- HTTP 403
- HTTP 429
- quota / credits / insufficient balance
- free-tier denial
- provider access restriction

Fallback should not happen for:

- prompt/schema bugs
- local parsing/validation bugs
- business logic errors
- malformed request payloads caused by our code

## File Changes

Primary files expected:

- `backend/app/config.py`
  - extend settings/config helpers as needed
- `backend/app/llm.py`
  - add chain parsing, candidate resolution, and sequential fallback execution
- `backend/app/schemas/models.py`
  - add typed models for fallback chain entries if needed
- `backend/app/routers/config.py`
  - keep old behavior working; optionally surface chain config in API responses later
- `backend/tests/unit/`
  - add tests for config parsing and fallback execution order

## Testing Strategy

Minimum coverage:

1. Legacy single-provider config still resolves correctly
2. Chain config resolves into three ordered candidates
3. 403 on OpenRouter free falls through to NVIDIA
4. NVIDIA failure falls through to OpenRouter auto
5. Non-fallback-eligible error stops immediately
6. Disabled chain entry is skipped

## Non-Goals For This Iteration

- Frontend UI for editing fallback chain
- Full provider management UX redesign
- Persisting multiple named chains
- Automatic model discovery from provider APIs

## Recommendation

Implement this in two layers:

1. Add typed config-chain parsing with backward compatibility
2. Add sequential runtime fallback in `backend/app/llm.py`

This gives us the new behavior quickly while keeping the blast radius mostly inside backend configuration and LLM transport.
