import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import unittest
import uuid

import httpx
from playwright.sync_api import sync_playwright


ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"
BACKEND_DIR = ROOT_DIR / "backend"
BACKEND_RUNNER = BACKEND_DIR / "tests" / "smoke_backend_server.py"
TEMP_ROOT = ROOT_DIR / ".tmp-smoke-tests"

UPLOAD_PROMPT = "\u8bf7\u4e0a\u4f20\u4f60\u7684\u4e3b\u7b80\u5386"
UPLOAD_SUCCESS = "\u7b80\u5386\u4e0a\u4f20\u6210\u529f"
ACTION_DOWNLOAD_PDF = "\u4e0b\u8f7d ATS PDF"
ACTION_EVALUATE_JOB = "A-F \u804c\u4f4d\u8bc4\u4f30"
ACTION_SEARCH_SEEK = "SEEK \u641c\u7d22\u5c97\u4f4d"
ACTION_VIEW_PORTALS = "\u67e5\u770b Portals"
ACTION_EDIT_PORTALS = "\u66f4\u65b0 Portals"
ACTION_DELETE_THREAD = "\u5220\u9664\u5f53\u524d\u5bf9\u8bdd"
TOOL_PANEL_TITLE = "\u5e38\u7528\u529f\u80fd"


ACTION_VIEW_SCHEDULED_SCAN = "\u67e5\u770b\u81ea\u52a8\u626b\u63cf"
ACTION_EDIT_SCHEDULED_SCAN = "\u66f4\u65b0\u81ea\u52a8\u626b\u63cf"


def pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for_http(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code < 500:
                return
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Server did not become ready at {url}: {last_error}")


def write_stub_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")


def send_chat_message(page, text: str) -> None:
    textarea = page.locator("textarea").last
    textarea.fill(text)

    for selector in ("form button[type='submit']", "button[type='submit']"):
        buttons = page.locator(selector)
        candidates = []
        for index in range(buttons.count()):
            button = buttons.nth(index)
            try:
                disabled_attr = button.get_attribute("disabled")
                aria_disabled = button.get_attribute("aria-disabled")
                if (
                    button.is_visible()
                    and button.is_enabled()
                    and disabled_attr is None
                    and aria_disabled != "true"
                ):
                    box = button.bounding_box()
                    candidates.append((box["y"] if box else float("-inf"), button))
            except Exception:
                continue
        if candidates:
            button = max(candidates, key=lambda item: item[0])[1]
            button.scroll_into_view_if_needed()
            button.click(timeout=2000)
            return

    textarea.press("Control+Enter")


def click_latest_enabled_action(page, label: str) -> None:
    panel_buttons = page.locator(f"[data-tool-card-label='{label}']")
    for index in range(panel_buttons.count()):
        button = panel_buttons.nth(index)
        try:
            if button.is_visible() and button.is_enabled():
                button.scroll_into_view_if_needed()
                button.click(timeout=2000)
                return
        except Exception:
            continue

    deadline = time.time() + 20
    while time.time() < deadline:
        buttons = page.get_by_role("button", name=label)
        candidates = []
        for index in range(buttons.count()):
            button = buttons.nth(index)
            try:
                if button.is_visible() and button.is_enabled():
                    box = button.bounding_box()
                    candidates.append((box["y"] if box else float("-inf"), button))
            except Exception:
                continue
        if candidates:
            button = max(candidates, key=lambda item: item[0])[1]
            button.scroll_into_view_if_needed()
            button.click(timeout=2000)
            return
        page.wait_for_timeout(250)
    raise AssertionError(f"No enabled action button found for: {label}")


def get_backend_json(
    base_url: str,
    path: str,
    *,
    params: dict[str, str | int] | None = None,
) -> dict:
    response = httpx.get(f"{base_url}{path}", params=params, timeout=10.0)
    response.raise_for_status()
    return response.json()


def get_local_user_id(base_url: str) -> str:
    payload = get_backend_json(
        base_url,
        "/api/v1/chat/users/by-identifier/local-user",
    )
    return str(payload["id"])


def list_local_user_threads(base_url: str) -> list[dict]:
    payload = get_backend_json(
        base_url,
        "/api/v1/chat/threads",
        params={
            "user_id": get_local_user_id(base_url),
            "first": 20,
        },
    )
    return payload.get("data") or []


def wait_for_thread_count(base_url: str, expected_count: int, timeout_s: float = 20.0) -> list[dict]:
    deadline = time.time() + timeout_s
    last_threads: list[dict] = []
    while time.time() < deadline:
        last_threads = list_local_user_threads(base_url)
        if len(last_threads) == expected_count:
            return last_threads
        time.sleep(0.5)
    raise AssertionError(
        f"Expected {expected_count} thread(s) but found {len(last_threads)}: {last_threads}"
    )


def wait_for_portals_company(
    base_url: str,
    expected_name: str,
    timeout_s: float = 20.0,
) -> dict:
    deadline = time.time() + timeout_s
    last_payload: dict = {}
    while time.time() < deadline:
        last_payload = get_backend_json(base_url, "/api/v1/config/portals")
        companies = last_payload.get("tracked_companies") or []
        if companies and companies[0].get("name") == expected_name:
            return last_payload
        time.sleep(0.5)
    raise AssertionError(
        f"Expected first tracked company to be {expected_name!r}, got: {last_payload}"
    )


def wait_for_scheduled_scan_time(
    base_url: str,
    expected_time: str,
    timeout_s: float = 20.0,
) -> dict:
    deadline = time.time() + timeout_s
    last_payload: dict = {}
    while time.time() < deadline:
        last_payload = get_backend_json(base_url, "/api/v1/scheduled-scan/settings")
        if last_payload.get("config", {}).get("run_time_local") == expected_time:
            return last_payload
        time.sleep(0.5)
    raise AssertionError(
        f"Expected scheduled scan time {expected_time!r}, got: {last_payload}"
    )


class RealBackendSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp_root = TEMP_ROOT / f"chainlit-real-backend-smoke-{uuid.uuid4().hex[:8]}"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.backend_log_path = self.temp_root / "backend.log"
        self.frontend_log_path = self.temp_root / "frontend.log"
        self.backend_process: subprocess.Popen | None = None
        self.frontend_process: subprocess.Popen | None = None

    def tearDown(self) -> None:
        for process in (self.frontend_process, self.backend_process):
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_chainlit_flow_with_real_backend(self) -> None:
        backend_port = pick_free_port()
        frontend_port = pick_free_port()
        backend_url = f"http://127.0.0.1:{backend_port}"
        frontend_url = f"http://127.0.0.1:{frontend_port}"
        resume_path = self.temp_root / "master_resume.pdf"
        write_stub_pdf(resume_path)

        backend_env = os.environ.copy()
        backend_env.update(
            {
                "DATA_DIR": str(self.temp_root / "backend-data"),
                "HOST": "127.0.0.1",
                "PORT": str(backend_port),
                "LOG_LEVEL": "ERROR",
            }
        )

        frontend_env = os.environ.copy()
        frontend_env.update(
            {
                "BACKEND_URL": backend_url,
                "CHAINLIT_APP_DATA_DIR": str(self.temp_root / "frontend-data"),
                "CHAINLIT_APP_PUBLIC_DIR": str(self.temp_root / "frontend-public"),
                "CHAINLIT_AUTO_LOGIN": "true",
                "CHAINLIT_APP_USERNAME": "local-user",
                "CHAINLIT_APP_PASSWORD": "job-mediator-123",
                "CHAINLIT_AUTH_SECRET": "local-dev-secret-change-me-2026-very-long",
            }
        )

        with self.backend_log_path.open("w", encoding="utf-8") as backend_log:
            self.backend_process = subprocess.Popen(
                [
                    "python",
                    str(BACKEND_RUNNER),
                    "--port",
                    str(backend_port),
                ],
                cwd=BACKEND_DIR,
                env=backend_env,
                stdout=backend_log,
                stderr=subprocess.STDOUT,
                text=True,
            )

        wait_for_http(backend_url)

        with self.frontend_log_path.open("w", encoding="utf-8") as frontend_log:
            self.frontend_process = subprocess.Popen(
                [
                    "chainlit",
                    "run",
                    "app.py",
                    "--headless",
                    "--ci",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(frontend_port),
                ],
                cwd=FRONTEND_DIR,
                env=frontend_env,
                stdout=frontend_log,
                stderr=subprocess.STDOUT,
                text=True,
            )

        wait_for_http(frontend_url)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(frontend_url, wait_until="domcontentloaded")

                page.locator("#ask-button-input").wait_for(timeout=20000)
                page.get_by_text(TOOL_PANEL_TITLE, exact=False).wait_for(timeout=20000)
                page.locator("[data-tool-card-label='SEEK 搜索岗位']").wait_for(timeout=20000)
                page.locator("#ask-button-input").set_input_files(str(resume_path))
                page.get_by_text(UPLOAD_SUCCESS, exact=False).wait_for(timeout=20000)
                page.wait_for_timeout(2000)

                send_chat_message(
                    page,
                    "Responsibilities: build APIs\nRequirements: Python and FastAPI",
                )

                page.get_by_text("tailored_resume.md", exact=False).wait_for(timeout=30000)
                page.get_by_text("tailored_resume.md", exact=False).wait_for(timeout=30000)
                click_latest_enabled_action(page, ACTION_DOWNLOAD_PDF)
                page.get_by_text("tailored_resume.pdf", exact=False).wait_for(timeout=20000)
                browser.close()
        except Exception as exc:  # pragma: no cover - diagnostic path
            backend_log = self.backend_log_path.read_text(encoding="utf-8", errors="ignore")
            frontend_log = self.frontend_log_path.read_text(encoding="utf-8", errors="ignore")
            page_snapshot = ""
            if "page" in locals():
                try:
                    page_snapshot = page.content()
                except Exception:
                    page_snapshot = "<unable to capture page text>"
            raise AssertionError(
                "Real backend smoke failed.\n\n"
                f"Backend log:\n{backend_log}\n\n"
                f"Frontend log:\n{frontend_log}\n\n"
                f"Page text:\n{page_snapshot}"
            ) from exc

    def test_chainlit_actions_flow_with_real_backend(self) -> None:
        backend_port = pick_free_port()
        frontend_port = pick_free_port()
        backend_url = f"http://127.0.0.1:{backend_port}"
        frontend_url = f"http://127.0.0.1:{frontend_port}"
        resume_path = self.temp_root / "master_resume.pdf"
        write_stub_pdf(resume_path)

        backend_env = os.environ.copy()
        backend_env.update(
            {
                "DATA_DIR": str(self.temp_root / "backend-data"),
                "HOST": "127.0.0.1",
                "PORT": str(backend_port),
                "LOG_LEVEL": "ERROR",
            }
        )

        frontend_env = os.environ.copy()
        frontend_env.update(
            {
                "BACKEND_URL": backend_url,
                "CHAINLIT_APP_DATA_DIR": str(self.temp_root / "frontend-data"),
                "CHAINLIT_APP_PUBLIC_DIR": str(self.temp_root / "frontend-public"),
                "CHAINLIT_AUTO_LOGIN": "true",
                "CHAINLIT_APP_USERNAME": "local-user",
                "CHAINLIT_APP_PASSWORD": "job-mediator-123",
                "CHAINLIT_AUTH_SECRET": "local-dev-secret-change-me-2026-very-long",
            }
        )

        with self.backend_log_path.open("w", encoding="utf-8") as backend_log:
            self.backend_process = subprocess.Popen(
                [
                    "python",
                    str(BACKEND_RUNNER),
                    "--port",
                    str(backend_port),
                ],
                cwd=BACKEND_DIR,
                env=backend_env,
                stdout=backend_log,
                stderr=subprocess.STDOUT,
                text=True,
            )

        wait_for_http(backend_url)

        with self.frontend_log_path.open("w", encoding="utf-8") as frontend_log:
            self.frontend_process = subprocess.Popen(
                [
                    "chainlit",
                    "run",
                    "app.py",
                    "--headless",
                    "--ci",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(frontend_port),
                ],
                cwd=FRONTEND_DIR,
                env=frontend_env,
                stdout=frontend_log,
                stderr=subprocess.STDOUT,
                text=True,
            )

        wait_for_http(frontend_url)

        jd_text = (
            "Responsibilities: build APIs\n"
            "Requirements: Python and FastAPI\n"
            "Qualifications: 5+ years backend engineering"
        )
        updated_portals_yaml = (
            '{"title_filter":{"positive":["platform","backend"],'
            '"negative":["intern"],"seniority_boost":["senior"]},'
            '"search_queries":[{"name":"platform","query":"platform backend engineer",'
            '"enabled":true}],"tracked_companies":[{"name":"OpenAI",'
            '"careers_url":"https://jobs.ashbyhq.com/openai","enabled":true,'
            '"api":"ashby"}]}'
        )
        rebuilt_thread_jd = (
            "Responsibilities: rebuild APIs\n"
            "Requirements: Python and FastAPI\n"
            "Qualifications: experience with platform systems"
        )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(frontend_url, wait_until="networkidle")

                page.get_by_text(UPLOAD_PROMPT, exact=False).wait_for(timeout=20000)
                page.locator("#ask-button-input").set_input_files(str(resume_path))
                page.get_by_text(UPLOAD_SUCCESS, exact=False).wait_for(timeout=20000)
                page.wait_for_timeout(2000)

                click_latest_enabled_action(page, ACTION_EVALUATE_JOB)
                page.get_by_text("\u628a\u76ee\u6807 JD \u76f4\u63a5\u8d34\u7ed9\u6211", exact=False).wait_for(timeout=20000)
                page.wait_for_timeout(1000)
                send_chat_message(page, jd_text)
                page.get_by_text("Strong backend fit in smoke mode.", exact=False).wait_for(
                    timeout=30000
                )
                page.get_by_text("\u5e02\u573a\u4fe1\u53f7", exact=False).wait_for(timeout=30000)
                page.get_by_text("Mock market source", exact=False).wait_for(timeout=30000)

                click_latest_enabled_action(page, ACTION_SEARCH_SEEK)
                page.get_by_text("SEEK \u641c\u7d22\u9762\u677f", exact=False).wait_for(timeout=30000)
                page.get_by_text("\u804c\u4f4d\u5361\u7247", exact=False).wait_for(timeout=30000)
                page.get_by_text("Example Co", exact=False).wait_for(timeout=30000)

                click_latest_enabled_action(page, ACTION_VIEW_PORTALS)
                page.get_by_text("Portals \u914d\u7f6e\u5df2\u5c31\u7eea", exact=False).wait_for(timeout=20000)
                page.wait_for_timeout(3000)

                click_latest_enabled_action(page, ACTION_EDIT_PORTALS)
                page.get_by_text("\u628a\u66f4\u65b0\u540e\u7684 portals YAML/JSON \u76f4\u63a5\u8d34\u7ed9\u6211", exact=False).wait_for(
                    timeout=30000
                )
                page.wait_for_timeout(1000)
                send_chat_message(page, updated_portals_yaml)
                page.get_by_text("OpenAI", exact=False).wait_for(timeout=20000)

                portals_payload = wait_for_portals_company(backend_url, "OpenAI")
                self.assertEqual(
                    portals_payload["tracked_companies"][0]["name"],
                    "OpenAI",
                )

                click_latest_enabled_action(page, ACTION_VIEW_SCHEDULED_SCAN)
                page.get_by_role("heading", name="\u81ea\u52a8\u626b\u63cf\u8bbe\u7f6e").wait_for(timeout=20000)
                page.get_by_text("\u82f1\u6587\u7b80\u5386 / SEEK", exact=False).wait_for(timeout=20000)

                click_latest_enabled_action(page, ACTION_EDIT_SCHEDULED_SCAN)
                page.get_by_text("\u5f53\u524d\u8bbe\u7f6e", exact=False).wait_for(timeout=30000)
                page.wait_for_timeout(1000)
                send_chat_message(
                    page,
                    "enabled: true\nrun_time_local: '21:30'\ntimezone: Australia/Sydney\nseek_enabled: true\ndoda_enabled: false\nboss_enabled: false",
                )
                page.get_by_text("21:30", exact=False).wait_for(timeout=20000)

                scheduled_payload = wait_for_scheduled_scan_time(backend_url, "21:30")
                self.assertEqual(
                    scheduled_payload["config"]["run_time_local"],
                    "21:30",
                )

                self.assertEqual(len(wait_for_thread_count(backend_url, 1)), 1)
                page.wait_for_timeout(3000)
                click_latest_enabled_action(page, ACTION_DELETE_THREAD)
                page.get_by_text("\u5f53\u524d\u5bf9\u8bdd\u5386\u53f2\u5df2\u7ecf\u6e05\u7a7a", exact=False).wait_for(timeout=20000)
                self.assertEqual(len(wait_for_thread_count(backend_url, 0)), 0)

                send_chat_message(page, rebuilt_thread_jd)
                page.get_by_text("tailored_resume.md", exact=False).wait_for(timeout=30000)
                page.get_by_text("tailored_resume.md", exact=False).wait_for(timeout=30000)

                rebuilt_threads = wait_for_thread_count(backend_url, 1)
                self.assertIn("Responsibilities: rebuild APIs", rebuilt_threads[0]["name"])
                browser.close()
        except Exception as exc:  # pragma: no cover - diagnostic path
            backend_log = self.backend_log_path.read_text(encoding="utf-8", errors="ignore")
            frontend_log = self.frontend_log_path.read_text(encoding="utf-8", errors="ignore")
            page_snapshot = ""
            if "page" in locals():
                try:
                    page_snapshot = page.content()
                except Exception:
                    page_snapshot = "<unable to capture page text>"
            raise AssertionError(
                "Real backend action smoke failed.\n\n"
                f"Backend log:\n{backend_log}\n\n"
                f"Frontend log:\n{frontend_log}\n\n"
                f"Page text:\n{page_snapshot}"
            ) from exc


if __name__ == "__main__":
    unittest.main()

