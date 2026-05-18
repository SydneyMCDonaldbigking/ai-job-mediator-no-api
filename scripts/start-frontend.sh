#!/usr/bin/env bash
set -euo pipefail

HOST_ADDRESS="${HOST_ADDRESS:-127.0.0.1}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"
BACKEND_URL_VALUE="${BACKEND_URL:-}"

if [[ -z "$BACKEND_URL_VALUE" ]]; then
  BACKEND_URL_VALUE="http://127.0.0.1:${BACKEND_PORT:-${PORT:-8001}}"
fi

if ! command -v python >/dev/null 2>&1; then
  echo "Python is not available on PATH." >&2
  exit 1
fi

export BACKEND_URL="$BACKEND_URL_VALUE"
export CHAINLIT_AUTH_SECRET="${CHAINLIT_AUTH_SECRET:-local-dev-secret-change-me-2026-very-long}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/frontend"

echo "Starting frontend on http://${HOST_ADDRESS}:${FRONTEND_PORT}"
echo "Using backend $BACKEND_URL_VALUE"
python -m chainlit run app.py --headless --host "$HOST_ADDRESS" --port "$FRONTEND_PORT"
