import importlib.util
from pathlib import Path
import unittest


FRONTEND_DIR = Path(__file__).resolve().parent
APP_PATH = FRONTEND_DIR / "app.py"


def load_frontend_app_module():
    spec = importlib.util.spec_from_file_location("frontend_app_module", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class AutoLoginScriptTests(unittest.TestCase):
    def test_auto_login_redirects_to_app_root_instead_of_login_path(self):
        frontend_app = load_frontend_app_module()
        frontend_app.ensure_runtime_assets()

        script = (frontend_app.PUBLIC_DIR / "auto-login.js").read_text(encoding="utf-8")

        self.assertIn("window.location.origin", script)
        self.assertNotIn("window.location.pathname + window.location.search + window.location.hash", script)

    def test_auto_login_only_submits_on_login_page_and_can_retry_after_failure(self):
        frontend_app = load_frontend_app_module()
        frontend_app.ensure_runtime_assets()

        script = (frontend_app.PUBLIC_DIR / "auto-login.js").read_text(encoding="utf-8")

        self.assertIn("window.location.pathname", script)
        self.assertIn('sessionStorage.removeItem(attemptKey);', script)
        self.assertIn('console.warn("Local auto-login failed."', script)


if __name__ == "__main__":
    unittest.main()
