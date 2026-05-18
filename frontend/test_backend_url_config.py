import importlib.util
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


FRONTEND_DIR = Path(__file__).resolve().parent
APP_PATH = FRONTEND_DIR / "app.py"


def load_frontend_app_module():
    if str(FRONTEND_DIR) not in sys.path:
        sys.path.insert(0, str(FRONTEND_DIR))
    spec = importlib.util.spec_from_file_location("frontend_app_backend_url_module", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class BackendUrlConfigTests(unittest.TestCase):
    def test_backend_url_defaults_to_127_0_0_1_8001(self):
        with patch.dict(
            os.environ,
            {
                "CHAINLIT_APP_PUBLIC_DIR": str(FRONTEND_DIR / ".tmp-tests" / "public-default"),
                "CHAINLIT_APP_DATA_DIR": str(FRONTEND_DIR / ".tmp-tests" / "data-default"),
            },
            clear=False,
        ):
            with patch.dict(os.environ, {"BACKEND_URL": "", "BACKEND_PORT": "", "PORT": ""}):
                module = load_frontend_app_module()

        self.assertEqual(module.BACKEND_URL, "http://127.0.0.1:8001")

    def test_backend_url_uses_backend_url_env_when_present(self):
        with patch.dict(
            os.environ,
            {
                "BACKEND_URL": "http://127.0.0.1:9555/",
                "CHAINLIT_APP_PUBLIC_DIR": str(FRONTEND_DIR / ".tmp-tests" / "public-explicit"),
                "CHAINLIT_APP_DATA_DIR": str(FRONTEND_DIR / ".tmp-tests" / "data-explicit"),
            },
            clear=False,
        ):
            module = load_frontend_app_module()

        self.assertEqual(module.BACKEND_URL, "http://127.0.0.1:9555")

    def test_backend_url_uses_backend_port_before_port(self):
        with patch.dict(
            os.environ,
            {
                "BACKEND_URL": "",
                "BACKEND_PORT": "9333",
                "PORT": "9444",
                "CHAINLIT_APP_PUBLIC_DIR": str(FRONTEND_DIR / ".tmp-tests" / "public-backend-port"),
                "CHAINLIT_APP_DATA_DIR": str(FRONTEND_DIR / ".tmp-tests" / "data-backend-port"),
            },
            clear=False,
        ):
            module = load_frontend_app_module()

        self.assertEqual(module.BACKEND_URL, "http://127.0.0.1:9333")
