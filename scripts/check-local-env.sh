#!/usr/bin/env bash
set -euo pipefail

echo "Checking local environment..."

if ! command -v python >/dev/null 2>&1; then
  echo "Python is not available on PATH." >&2
  exit 1
fi

python --version

missing=0
for module in uvicorn fastapi litellm chainlit playwright; do
  if python -c "import ${module}" >/dev/null 2>&1; then
    echo "[ok] Python module '${module}'"
  else
    echo "[missing] Python module '${module}'"
    missing=1
  fi
done

if python -m playwright install --dry-run chromium >/dev/null 2>&1; then
  echo "[ok] Playwright Chromium is installed or installable"
else
  echo "[warn] Playwright Chromium may be missing. Run: python -m playwright install chromium"
fi

RESOLVED_PORT="${BACKEND_PORT:-${PORT:-8001}}"
RESOLVED_BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:${RESOLVED_PORT}}"

echo
echo "Resolved backend port: ${RESOLVED_PORT}"
echo "Resolved backend URL: ${RESOLVED_BACKEND_URL}"

if [[ "$missing" -ne 0 ]]; then
  echo
  echo "Install missing dependencies before starting the app."
fi
