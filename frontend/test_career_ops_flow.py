import importlib.util
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import patch


FRONTEND_DIR = Path(__file__).resolve().parent
APP_PATH = FRONTEND_DIR / "app.py"


def load_frontend_app_module():
    if str(FRONTEND_DIR) not in sys.path:
        sys.path.insert(0, str(FRONTEND_DIR))
    spec = importlib.util.spec_from_file_location("frontend_app_flow_module", APP_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeUserSession:
    def __init__(self):
        self.values = {}

    def get(self, key, default=None):
        return self.values.get(key, default)

    def set(self, key, value):
        self.values[key] = value


class FakeDataLayer:
    def __init__(self):
        self.thread_updates = []
        self.deleted_threads = []

    async def update_thread(self, **kwargs):
        self.thread_updates.append(dict(kwargs))

    async def delete_thread(self, thread_id: str):
        self.deleted_threads.append(thread_id)

    async def get_thread(self, thread_id: str):
        return None


class FakeBackend:
    def __init__(self, frontend_app=None):
        self.frontend_app = frontend_app
        self.current_resume_content = "# Master Resume"
        self.upload_calls = []
        self.job_uploads = []
        self.improve_calls = []
        self.generated_payloads = []

    async def upload_resume(
        self,
        file_path: str,
        file_name: str,
        mime_type: str,
        resume_language: str = "en",
    ):
        self.upload_calls.append(
            {
                "file_path": file_path,
                "file_name": file_name,
                "mime_type": mime_type,
                "resume_language": resume_language,
            }
        )
        self.current_resume_content = (
            "# Master Resume V2" if "v2" in file_name.lower() else "# Master Resume V1"
        )

        if self.frontend_app is not None:
            return self.frontend_app.ResumeUploadResponse.model_validate(
                {
                    "message": "uploaded",
                    "request_id": f"upload-{len(self.upload_calls)}",
                    "resume_id": "master-123",
                    "processing_status": "ready",
                    "is_master": True,
                }
            )

        return SimpleNamespace(
            message="uploaded",
            request_id=f"upload-{len(self.upload_calls)}",
            resume_id="master-123",
            processing_status="ready",
            is_master=True,
        )

    async def get_resume_status(self, resume_id: str) -> str:
        return "ready"

    async def get_resume_content(self, resume_id: str) -> str:
        return self.current_resume_content

    async def upload_job_description(self, resume_id: str, job_description: str) -> str:
        self.job_uploads.append(
            {
                "resume_id": resume_id,
                "job_description": job_description,
            }
        )
        return f"job-{len(self.job_uploads)}"

    async def improve_resume(self, resume_id: str, job_id: str):
        self.improve_calls.append({"resume_id": resume_id, "job_id": job_id})
        if self.frontend_app is not None:
            return self.frontend_app.ImproveResumeResponse.model_validate(
                {
                    "request_id": f"improve-{len(self.improve_calls)}",
                    "data": {
                        "resume_id": f"tailored-{len(self.improve_calls)}",
                        "job_id": job_id,
                        "improvements": [],
                        "markdownImproved": f"{self.current_resume_content}\n\nTailored",
                        "cover_letter": None,
                        "outreach_message": None,
                        "diff_summary": None,
                        "refinement_stats": None,
                        "warnings": [],
                    },
                }
            )

        return SimpleNamespace(
            request_id=f"improve-{len(self.improve_calls)}",
            data=SimpleNamespace(
                resume_id=f"tailored-{len(self.improve_calls)}",
                job_id=job_id,
                improvements=[],
                markdownImproved=f"{self.current_resume_content}\n\nTailored",
                cover_letter=None,
                outreach_message=None,
                diff_summary=None,
                refinement_stats=None,
                warnings=[],
            ),
        )

    async def generate_tailored_pdf(self, resume: str, job_description: str):
        self.generated_payloads.append(
            {
                "resume": resume,
                "job_description": job_description,
            }
        )
        return {
            "filename": "tailored_resume.pdf",
            "content": b"%PDF-1.4\nfake\n",
        }


class FakeFile:
    def __init__(self, name: str, content: bytes, display: str, mime: str | None = None):
        self.name = name
        self.content = content
        self.display = display
        self.mime = mime


class FakeAskFileMessage:
    responses = []
    prompts = []

    def __init__(self, content="", **kwargs):
        self.content = content
        self.kwargs = kwargs
        FakeAskFileMessage.prompts.append(content)

    async def send(self):
        if not FakeAskFileMessage.responses:
            return None
        return FakeAskFileMessage.responses.pop(0)


class FakeMessage:
    created = []

    def __init__(self, content="", actions=None, elements=None):
        self.content = content
        self.actions = actions
        self.elements = elements or []
        self.sent = False
        self.updated = False
        FakeMessage.created.append(self)

    async def send(self):
        self.sent = True
        return self

    async def update(self):
        self.updated = True
        return self


class CareerOpsFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_then_pdf_request_recreates_thread_with_user_binding(self):
        frontend_app = load_frontend_app_module()
        fake_user_session = FakeUserSession()
        fake_user_session.set(frontend_app.SESSION_RESUME_ID, "master-123")
        fake_user_session.set(frontend_app.SESSION_RESUME_STATUS, "ready")
        fake_user_session.set(frontend_app.SESSION_LAST_JOB_DESCRIPTION, "old jd")
        fake_user_session.set(frontend_app.SESSION_THREAD_NAMED, True)
        fake_user_session.set(frontend_app.SESSION_PENDING_ACTION, None)

        fake_data_layer = FakeDataLayer()
        fake_backend = FakeBackend()
        fake_context = SimpleNamespace(
            session=SimpleNamespace(
                thread_id="thread-1",
                user=SimpleNamespace(id="user-1", identifier="local-user"),
            )
        )
        jd_text = "Responsibilities: build APIs\nRequirements: Python and FastAPI"

        FakeMessage.created = []

        with (
            patch.object(frontend_app.cl, "user_session", fake_user_session),
            patch.object(frontend_app.cl, "Message", FakeMessage),
            patch.object(frontend_app.cl, "File", FakeFile),
            patch.object(frontend_app, "build_tool_actions", return_value=[]),
            patch.object(frontend_app, "data_layer", fake_data_layer),
            patch.object(frontend_app, "backend", fake_backend),
            patch.object(frontend_app, "context", fake_context),
        ):
            await frontend_app.on_delete_current_thread_action(None)
            await frontend_app.on_download_tailored_pdf_action(None)
            await frontend_app.on_message(
                SimpleNamespace(content=jd_text, elements=None)
            )

        self.assertEqual(fake_data_layer.deleted_threads, ["thread-1"])
        self.assertEqual(
            fake_user_session.get(frontend_app.SESSION_PENDING_ACTION),
            None,
        )
        self.assertEqual(
            fake_user_session.get(frontend_app.SESSION_LAST_JOB_DESCRIPTION),
            jd_text,
        )
        self.assertEqual(
            fake_backend.generated_payloads,
            [{"resume": "# Master Resume", "job_description": jd_text}],
        )
        self.assertGreaterEqual(len(fake_data_layer.thread_updates), 2)
        self.assertTrue(
            all(call.get("user_id") == "user-1" for call in fake_data_layer.thread_updates)
        )
        self.assertEqual(FakeMessage.created[-1].elements[0].name, "tailored_resume.pdf")

    async def test_full_primary_flow_supports_reupload_pdf_and_recreate(self):
        frontend_app = load_frontend_app_module()
        fake_user_session = FakeUserSession()
        fake_data_layer = FakeDataLayer()
        fake_backend = FakeBackend(frontend_app)
        fake_context = SimpleNamespace(
            session=SimpleNamespace(
                thread_id="thread-main",
                user=SimpleNamespace(id="user-1", identifier="local-user"),
            )
        )
        first_resume = SimpleNamespace(
            path="C:/tmp/master_v1.pdf",
            name="master_v1.pdf",
            mime="application/pdf",
        )
        second_resume = SimpleNamespace(
            path="C:/tmp/master_v2.docx",
            name="master_v2.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        first_jd = "Responsibilities: build APIs\nRequirements: Python and FastAPI"
        second_jd = (
            "Responsibilities: scale services\n"
            "Requirements: Python and distributed systems"
        )

        FakeAskFileMessage.responses = [[first_resume], [second_resume]]
        FakeAskFileMessage.prompts = []
        FakeMessage.created = []

        with (
            patch.object(frontend_app.cl, "user_session", fake_user_session),
            patch.object(frontend_app.cl, "Message", FakeMessage),
            patch.object(frontend_app.cl, "File", FakeFile),
            patch.object(frontend_app.cl, "AskFileMessage", FakeAskFileMessage),
            patch.object(frontend_app, "build_tool_actions", return_value=[]),
            patch.object(frontend_app, "data_layer", fake_data_layer),
            patch.object(frontend_app, "backend", fake_backend),
            patch.object(frontend_app, "context", fake_context),
        ):
            await frontend_app.on_chat_start()
            await frontend_app.on_message(SimpleNamespace(content=first_jd, elements=None))
            await frontend_app.on_download_tailored_pdf_action(None)
            await frontend_app.on_reupload_master_resume_action(None)
            await frontend_app.on_download_tailored_pdf_action(None)
            await frontend_app.on_delete_current_thread_action(None)
            await frontend_app.on_message(SimpleNamespace(content=second_jd, elements=None))

        self.assertEqual(
            [call["file_name"] for call in fake_backend.upload_calls],
            ["master_v1.pdf", "master_v2.docx"],
        )
        self.assertEqual(
            [call["resume"] for call in fake_backend.generated_payloads],
            ["# Master Resume V1", "# Master Resume V2"],
        )
        self.assertEqual(
            [call["job_description"] for call in fake_backend.generated_payloads],
            [first_jd, first_jd],
        )
        self.assertEqual(
            [call["job_description"] for call in fake_backend.job_uploads],
            [first_jd, second_jd],
        )
        self.assertEqual(fake_user_session.get(frontend_app.SESSION_RESUME_ID), "master-123")
        self.assertEqual(
            fake_user_session.get(frontend_app.SESSION_LAST_UPLOAD_NAME),
            "master_v2.docx",
        )
        self.assertEqual(
            fake_user_session.get(frontend_app.SESSION_LAST_JOB_DESCRIPTION),
            second_jd,
        )
        self.assertEqual(
            fake_user_session.get(frontend_app.SESSION_LAST_TAILORED_RESUME_ID),
            "tailored-2",
        )
        self.assertEqual(fake_data_layer.deleted_threads, ["thread-main"])
        self.assertGreaterEqual(len(fake_data_layer.thread_updates), 6)
        self.assertTrue(
            all(call.get("user_id") == "user-1" for call in fake_data_layer.thread_updates)
        )
        self.assertEqual(len(FakeAskFileMessage.prompts), 2)
        self.assertNotEqual(FakeAskFileMessage.prompts[0], FakeAskFileMessage.prompts[1])
        pdf_messages = [
            message
            for message in FakeMessage.created
            if message.elements and message.elements[0].name == "tailored_resume.pdf"
        ]
        self.assertEqual(len(pdf_messages), 2)


if __name__ == "__main__":
    unittest.main()
