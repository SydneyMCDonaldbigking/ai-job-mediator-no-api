from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]

BACKEND_TESTS = [
    "backend/tests/integration/test_chat_history_api.py",
    "backend/tests/integration/test_portals_config_api.py",
    "backend/tests/integration/test_seek_search_api.py",
    "backend/tests/integration/test_scheduled_scan_api.py",
    "backend/tests/unit/test_seek_search_service.py",
    "backend/tests/unit/test_scheduled_scan_service.py",
]

FRONTEND_TESTS = [
    "frontend/test_backend_chat_store.py",
    "frontend/test_career_ops_frontend.py",
    "frontend/test_career_ops_flow.py",
    "frontend/test_browser_smoke.py",
    "frontend/test_real_backend_smoke.py",
]


def run_command(label: str, command: list[str]) -> None:
    print(f"\n==> {label}", flush=True)
    print(" ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT_DIR, check=True)


def main() -> int:
    run_command(
        "Backend integration checks",
        [sys.executable, "-m", "pytest", *BACKEND_TESTS, "-v"],
    )
    run_command(
        "Frontend browser and real-backend smoke checks",
        [sys.executable, "-m", "unittest", *FRONTEND_TESTS, "-v"],
    )
    print("\nCareer Ops CI checks completed successfully.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
