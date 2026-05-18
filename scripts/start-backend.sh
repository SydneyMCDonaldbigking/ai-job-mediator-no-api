#!/usr/bin/env bash
set -euo pipefail

HOST_ADDRESS="${HOST_ADDRESS:-127.0.0.1}"
BACKEND_PORT_VALUE="${BACKEND_PORT:-${PORT:-8001}}"

if [[ $# -ge 1 ]]; then
  BACKEND_PORT_VALUE="$1"
fi

if ! command -v python >/dev/null 2>&1; then
  echo "Python is not available on PATH." >&2
  exit 1
fi

export BACKEND_PORT="$BACKEND_PORT_VALUE"
export PORT="${PORT:-$BACKEND_PORT_VALUE}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT/backend"

echo "Starting backend on http://${HOST_ADDRESS}:${BACKEND_PORT_VALUE}"
python -m uvicorn app.main:app --host "$HOST_ADDRESS" --port "$BACKEND_PORT_VALUE"
