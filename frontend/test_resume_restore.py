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


class FakeSession:
    def __init__(self):
        self.values = {}

    def set(self, key, value):
        self.values[key] = value


class ResumeRestoreTests(unittest.TestCase):
    def test_apply_thread_metadata_to_session_restores_resume_state(self):
        frontend_app = load_frontend_app_module()
        session = FakeSession()

        restored = frontend_app.apply_thread_metadata_to_session(
            {
                "metadata": {
                    "resume_id": "resume-123",
                    "resume_status": "ready",
                    "last_upload_name": "resume.docx",
                    "tailored_resume_id": "tailored-456",
                    "thread_named": False,
                },
                "name": "Existing thread",
            },
            session,
        )

        self.assertTrue(restored)
        self.assertEqual(session.values["resume_id"], "resume-123")
        self.assertEqual(session.values["resume_status"], "ready")
        self.assertEqual(session.values["last_upload_name"], "resume.docx")
        self.assertEqual(session.values["tailored_resume_id"], "tailored-456")
        self.assertFalse(session.values["thread_named"])


if __name__ == "__main__":
    unittest.main()
