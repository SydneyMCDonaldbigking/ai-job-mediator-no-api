# Backend Data Configuration

This directory holds runtime data and configuration for the backend.

## Files

- `config.example.json`
  Safe example for LLM runtime configuration, API-key slot names, and fallback-chain structure.
- `config.json`
  Real local runtime configuration. This may contain secrets and is intentionally ignored by git.
- `portals.example.yml`
  Safe example for portal-scanning configuration.
- `portals.yml`
  Active local portal-scanning configuration.

## Configuration Split

The project uses two main configuration layers:

### 1. Root `.env`

Use the root `.env` for:

- host / port binding
- backend public URL
- frontend backend target
- simple single-provider LLM overrides
- local app auth defaults

Examples:

- `BACKEND_PORT`
- `PORT`
- `BACKEND_URL`
- `FRONTEND_BASE_URL`
- `LLM_PROVIDER`
- `LLM_MODEL`
- `LLM_API_KEY`

### 2. `backend/data/config.json`

Use `config.json` for backend runtime settings that are saved, edited, or read by the app itself:

- provider selection
- model selection
- provider-specific API keys
- fallback-chain entries
- feature toggles
- language preferences
- prompt selection

If `llm_fallback_chain` is present, it is the runtime source of truth for multi-provider LLM fallback.

## Recommended Local Workflow

1. Copy `.env.example` to `.env`
2. Set:
   - `BACKEND_PORT=8001`
   - `BACKEND_URL=http://127.0.0.1:8001`
   - `FRONTEND_BASE_URL=http://localhost:3000`
3. Copy `config.example.json` to `config.json`
4. Fill real API keys in `config.json`

## Dynamic Port Rule

Backend port priority:

1. `BACKEND_PORT`
2. `PORT`
3. default `8001`

Frontend/client examples should follow the same rule and resolve `BACKEND_URL` first if it is explicitly set.
