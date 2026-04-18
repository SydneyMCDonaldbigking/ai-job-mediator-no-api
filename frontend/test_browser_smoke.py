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


FRONTEND_DIR = Path(__file__).resolve().parent
TEMP_ROOT = FRONTEND_DIR.parent / ".tmp-smoke-tests"
UPLOAD_PROMPT = "\u8bf7\u4e0a\u4f20\u4f60\u7684\u4e3b\u7b80\u5386"
UPLOAD_SUCCESS = "\u7b80\u5386\u4e0a\u4f20\u6210\u529f"
ACTION_DOWNLOAD_PDF = "\u4e0b\u8f7d ATS PDF"
ACTION_REUPLOAD = "\u91cd\u65b0\u4e0a\u4f20\u4e3b\u7b80\u5386"
TOOL_PANEL_TITLE = "\u5e38\u7528\u529f\u80fd"


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


def write_stub_docx(path: Path) -> None:
    path.write_bytes(b"PK\x03\x04fake-docx")


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


class BrowserSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp_root = TEMP_ROOT / f"chainlit-browser-smoke-{uuid.uuid4().hex[:8]}"
        self.temp_root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.temp_root / "chainlit.log"
        self.process: subprocess.Popen | None = None

    def tearDown(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        shutil.rmtree(self.temp_root, ignore_errors=True)

    def test_chainlit_primary_flow_in_browser(self) -> None:
        port = pick_free_port()
        base_url = f"http://127.0.0.1:{port}"
        pdf_path = self.temp_root / "master_v1.pdf"
        docx_path = self.temp_root / "master_v2.docx"
        write_stub_pdf(pdf_path)
        write_stub_docx(docx_path)

        env = os.environ.copy()
        env.update(
            {
                "CHAINLIT_TEST_MODE": "1",
                "CHAINLIT_APP_DATA_DIR": str(self.temp_root / "data"),
                "CHAINLIT_APP_PUBLIC_DIR": str(self.temp_root / "public"),
                "CHAINLIT_AUTO_LOGIN": "true",
                "CHAINLIT_APP_USERNAME": "local-user",
                "CHAINLIT_APP_PASSWORD": "job-mediator-123",
                "CHAINLIT_AUTH_SECRET": "local-dev-secret-change-me-2026-very-long",
            }
        )

        with self.log_path.open("w", encoding="utf-8") as log_file:
            self.process = subprocess.Popen(
                [
                    "chainlit",
                    "run",
                    "app.py",
                    "--headless",
                    "--ci",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                ],
                cwd=FRONTEND_DIR,
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )

        wait_for_http(base_url)

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(base_url, wait_until="domcontentloaded")

                page.locator("#ask-button-input").wait_for(timeout=20000)
                page.get_by_text(TOOL_PANEL_TITLE, exact=False).wait_for(timeout=20000)
                page.locator("[data-tool-card-label='SEEK 搜索岗位']").wait_for(timeout=20000)
                page.locator("#ask-button-input").set_input_files(str(pdf_path))
                page.get_by_text(UPLOAD_SUCCESS, exact=False).wait_for(timeout=20000)

                send_chat_message(
                    page,
                    "Responsibilities: build APIs\nRequirements: Python and FastAPI",
                )
                page.get_by_text("tailored_resume.md", exact=False).wait_for(timeout=20000)

                click_latest_enabled_action(page, ACTION_DOWNLOAD_PDF)
                page.get_by_text("tailored_resume.pdf", exact=False).wait_for(timeout=20000)

                click_latest_enabled_action(page, ACTION_REUPLOAD)
                page.locator("#ask-button-input").set_input_files(str(docx_path))
                page.get_by_text(UPLOAD_SUCCESS, exact=False).wait_for(timeout=20000)

                send_chat_message(
                    page,
                    "Responsibilities: scale services\nRequirements: Python and distributed systems",
                )
                page.get_by_text("tailored resume_id", exact=False).wait_for(timeout=20000)
                browser.close()
        except Exception as exc:  # pragma: no cover - diagnostic path
            log_output = self.log_path.read_text(encoding="utf-8", errors="ignore")
            raise AssertionError(f"Browser smoke failed.\n\nChainlit log:\n{log_output}") from exc


if __name__ == "__main__":
    unittest.main()
