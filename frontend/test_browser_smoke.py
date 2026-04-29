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
UPLOAD_PROMPT = "请上传你的主简历"
UPLOAD_SUCCESS = "简历上传成功"
ACTION_DOWNLOAD_PDF = "下载 ATS PDF"
ACTION_REUPLOAD = "重新上传主简历"
ACTION_SEARCH_SEEK = "SEEK 搜索岗位"
ACTION_VIEW_SCHEDULED_SCAN = "查看自动扫描"
LOGIN_USERNAME = "local-user"
LOGIN_PASSWORD = "job-mediator-123"


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

    for selector in ("#chat-submit", "form button[type='submit']", "button[type='submit']"):
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


def authenticate_browser_context(browser, base_url: str):
    response = httpx.post(
        f"{base_url}/login",
        data={"username": LOGIN_USERNAME, "password": LOGIN_PASSWORD},
        timeout=10.0,
    )
    response.raise_for_status()
    token = response.cookies.get("access_token")
    if not token:
        raise AssertionError("Login did not return an access_token cookie.")
    context = browser.new_context()
    context.add_cookies(
        [
            {
                "name": "access_token",
                "value": token,
                "url": base_url,
                "httpOnly": False,
            }
        ]
    )
    return context


def wait_for_body_text(page, text: str, timeout: float = 20000) -> None:
    page.wait_for_function(
        "(expected) => document.body && document.body.innerText.includes(expected)",
        arg=text,
        timeout=timeout,
    )


def wait_for_current_tool_binding(page, label: str, timeout: float = 20000) -> None:
    page.wait_for_function(
        """
        (expected) => {
          const selector = `button[data-ai-job-tool-current="true"][data-ai-job-tool-label="${expected}"]`;
          return document.querySelectorAll(selector).length === 1;
        }
        """,
        arg=label,
        timeout=timeout,
    )


def wait_for_tool_card_status(page, label: str, status_text: str, timeout: float = 20000) -> None:
    page.locator(
        f"[data-tool-card-label='{label}'] .tool-card-status",
    ).first.wait_for(state="visible", timeout=timeout)
    page.wait_for_function(
        """
        ([label, expected]) => {
          const card = document.querySelector(`[data-tool-card-label="${label}"] .tool-card-status`);
          return card && card.textContent && card.textContent.includes(expected);
        }
        """,
        arg=[label, status_text],
        timeout=timeout,
    )


def wait_for_tool_card_meta(page, label: str, expected_text: str, timeout: float = 20000) -> None:
    page.locator(
        f"[data-tool-card-label='{label}'] .tool-card-meta",
    ).first.wait_for(state="visible", timeout=timeout)
    page.wait_for_function(
        """
        ([label, expected]) => {
          const card = document.querySelector(`[data-tool-card-label="${label}"] .tool-card-meta`);
          return card && card.textContent && card.textContent.includes(expected);
        }
        """,
        arg=[label, expected_text],
        timeout=timeout,
    )


def wait_for_tool_card_badge(page, label: str, expected_text: str, timeout: float = 20000) -> None:
    page.locator(
        f"[data-tool-card-label='{label}'] .tool-card-badge",
    ).first.wait_for(state="visible", timeout=timeout)
    page.wait_for_function(
        """
        ([label, expected]) => {
          const badge = document.querySelector(`[data-tool-card-label="${label}"] .tool-card-badge`);
          return badge && badge.textContent && badge.textContent.includes(expected);
        }
        """,
        arg=[label, expected_text],
        timeout=timeout,
    )


def wait_for_tool_card_tag(page, label: str, expected_text: str, timeout: float = 20000) -> None:
    page.locator(
        f"[data-tool-card-label='{label}'] .tool-card-tag",
    ).first.wait_for(state="visible", timeout=timeout)
    page.wait_for_function(
        """
        ([label, expected]) => {
          const tags = Array.from(
            document.querySelectorAll(`[data-tool-card-label="${label}"] .tool-card-tag`)
          );
          return tags.some((tag) => (tag.textContent || "").includes(expected));
        }
        """,
        arg=[label, expected_text],
        timeout=timeout,
    )


def wait_for_tool_card_priority(
    page,
    label: str,
    expected_priority: str,
    timeout: float = 20000,
) -> None:
    page.wait_for_function(
        """
        ([label, expected]) => {
          const card = document.querySelector(`[data-tool-card-label="${label}"]`);
          if (card) {
            return card.getAttribute("data-tool-card-priority") === expected;
          }
          if (expected === "primary") {
            return document.querySelectorAll('[data-tool-card-priority="primary"]').length > 0;
          }
          return false;
        }
        """,
        arg=[label, expected_priority],
        timeout=timeout,
    )


def wait_for_scan_results_title(page, title: str, timeout: float = 20000) -> None:
    page.wait_for_function(
        """
        (expected) => {
          const root = document.querySelector("[data-ai-job-scan-results='true']");
          return root && root.innerText.includes(expected);
        }
        """,
        arg=title,
        timeout=timeout,
    )


def wait_for_scan_results_title_absent(page, title: str, timeout: float = 20000) -> None:
    page.wait_for_function(
        """
        (expected) => {
          const root = document.querySelector("[data-ai-job-scan-results='true']");
          return !root || !root.innerText.includes(expected);
        }
        """,
        arg=title,
        timeout=timeout,
    )


def click_scan_result_action(page, action_label: str, timeout_s: float = 15.0) -> None:
    deadline = time.time() + timeout_s
    last_error = None
    while time.time() < deadline:
        try:
            clicked = page.evaluate(
                """
                (label) => {
                  const matches = Array.from(
                    document.querySelectorAll(`[data-job-apply-label="${label}"]`)
                  );
                  const button = matches[matches.length - 1];
                  if (!button) return false;
                  button.click();
                  return true;
                }
                """,
                action_label,
            )
            if clicked:
                return
        except Exception as exc:
            last_error = exc
            page.wait_for_timeout(250)
    raise AssertionError(f"Could not click scan result action: {action_label}\n{last_error}")


def get_body_text(page) -> str:
    return page.evaluate("() => document.body ? document.body.innerText : ''")


def upload_resume_with_retry(
    page,
    file_path: Path,
    success_text: str,
    *,
    max_attempts: int = 3,
    attempt_timeout_s: float = 8.0,
) -> None:
    file_input = page.locator("input[type='file']").first
    last_body = ""

    for attempt in range(max_attempts):
        file_input.set_input_files(str(file_path))
        deadline = time.time() + attempt_timeout_s

        while time.time() < deadline:
            last_body = get_body_text(page)
            if success_text in last_body:
                return
            if "Session not found" in last_body or "上传失败" in last_body:
                break
            page.wait_for_timeout(250)

        if attempt < max_attempts - 1:
            page.wait_for_timeout(2000)

    raise AssertionError(
        "Resume upload did not succeed in browser smoke.\n\n"
        f"Last page body:\n{last_body}"
    )


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
                context = authenticate_browser_context(browser, base_url)
                page = context.new_page()
                console_logs: list[str] = []
                page_errors: list[str] = []
                page.on("console", lambda message: console_logs.append(f"{message.type}: {message.text}"))
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(base_url, wait_until="domcontentloaded")

                file_input = page.locator("input[type='file']").first
                file_input.wait_for(state="attached", timeout=20000)
                page.locator(f"[data-tool-card-label='{ACTION_SEARCH_SEEK}']").first.wait_for(
                    state="attached",
                    timeout=20000,
                )
                wait_for_current_tool_binding(page, ACTION_SEARCH_SEEK, timeout=20000)
                wait_for_body_text(page, UPLOAD_PROMPT, timeout=20000)
                wait_for_tool_card_meta(page, ACTION_REUPLOAD, "打开上传框", timeout=20000)
                wait_for_tool_card_meta(page, ACTION_SEARCH_SEEK, "英文简历", timeout=20000)
                wait_for_tool_card_meta(page, "扫描职位", "已配置站点", timeout=20000)
                wait_for_tool_card_badge(page, ACTION_REUPLOAD, "上传", timeout=20000)
                wait_for_tool_card_badge(page, ACTION_SEARCH_SEEK, "搜索", timeout=20000)
                wait_for_tool_card_status(page, ACTION_SEARCH_SEEK, "可用", timeout=20000)
                wait_for_tool_card_priority(page, ACTION_REUPLOAD, "primary", timeout=20000)
                wait_for_tool_card_priority(page, "ä¸Šä¼ è‹±æ–‡ç®€åŽ†", "primary", timeout=20000)
                wait_for_tool_card_priority(page, ACTION_SEARCH_SEEK, "standard", timeout=20000)
                wait_for_tool_card_tag(page, ACTION_SEARCH_SEEK, "英文", timeout=20000)
                wait_for_tool_card_tag(page, ACTION_SEARCH_SEEK, "单站", timeout=20000)
                wait_for_tool_card_tag(page, "扫描职位", "批量", timeout=20000)
                wait_for_tool_card_tag(page, "扫描职位", "已配置", timeout=20000)
                wait_for_tool_card_tag(page, "扫描职位", "高分", timeout=20000)
                wait_for_tool_card_meta(page, "扫描职位", "新增岗位", timeout=20000)
                wait_for_tool_card_meta(page, "扫描职位", "高分未投递", timeout=20000)
                wait_for_tool_card_priority(page, "扫描职位", "workspace", timeout=20000)
                upload_resume_with_retry(page, pdf_path, UPLOAD_SUCCESS)
                wait_for_tool_card_status(page, ACTION_SEARCH_SEEK, "可用", timeout=20000)

                click_latest_enabled_action(page, ACTION_VIEW_SCHEDULED_SCAN)
                wait_for_scan_results_title(page, "Senior Backend Engineer", timeout=20000)
                wait_for_scan_results_title(page, "Staff Platform Engineer", timeout=20000)
                click_scan_result_action(
                    page,
                    "标记已投递: Example Co / Staff Platform Engineer",
                )
                wait_for_scan_results_title_absent(page, "Staff Platform Engineer", timeout=20000)

                send_chat_message(
                    page,
                    "Responsibilities: build APIs\nRequirements: Python and FastAPI",
                )
                wait_for_body_text(page, "tailored_resume.md", timeout=20000)

                click_latest_enabled_action(page, ACTION_DOWNLOAD_PDF)
                wait_for_body_text(page, "tailored_resume.pdf", timeout=20000)

                click_latest_enabled_action(page, ACTION_REUPLOAD)
                upload_resume_with_retry(page, docx_path, UPLOAD_SUCCESS)

                send_chat_message(
                    page,
                    "Responsibilities: scale services\nRequirements: Python and distributed systems",
                )
                wait_for_body_text(page, "tailored resume_id", timeout=20000)
                context.close()
                browser.close()
        except Exception as exc:  # pragma: no cover - diagnostic path
            log_output = self.log_path.read_text(encoding="utf-8", errors="ignore")
            page_snapshot = ""
            page_url = "<unavailable>"
            if "page" in locals():
                try:
                    page_url = page.url
                    page_snapshot = page.content()
                except Exception:
                    page_snapshot = "<unable to capture page text>"
            raise AssertionError(
                "Browser smoke failed.\n\n"
                f"Page URL:\n{page_url}\n\n"
                f"Page errors:\n{page_errors if 'page_errors' in locals() else []}\n\n"
                f"Console logs:\n{console_logs if 'console_logs' in locals() else []}\n\n"
                f"Page text:\n{page_snapshot}\n\n"
                f"Chainlit log:\n{log_output}"
            ) from exc


if __name__ == "__main__":
    unittest.main()
