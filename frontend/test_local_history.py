from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from chainlit.types import Pagination, ThreadFilter
from chainlit.user import User

from local_chat_store import LocalJsonDataLayer


class LocalJsonDataLayerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        temp_root = Path(__file__).resolve().parent / ".tmp-tests" / "local-history-test"
        shutil.rmtree(temp_root, ignore_errors=True)
        temp_root.mkdir(parents=True, exist_ok=True)
        self.base_dir = temp_root
        self.data_layer = LocalJsonDataLayer(
            data_dir=self.base_dir / "data",
            public_dir=self.base_dir / "public",
        )
        self.user = await self.data_layer.create_user(
            User(identifier="local-user", display_name="Local User")
        )
        assert self.user is not None

    async def asyncTearDown(self) -> None:
        await self.data_layer.close()
        shutil.rmtree(self.base_dir, ignore_errors=True)

    async def test_thread_round_trip_restores_resume_metadata(self) -> None:
        await self.data_layer.update_thread(
            thread_id="thread-1",
            name="First message title",
            user_id=self.user.id,
            metadata={
                "resume_id": "resume-123",
                "resume_status": "ready",
                "tailored_resume_id": "tailored-456",
            },
        )
        await self.data_layer.create_step(
            {
                "id": "step-user",
                "name": "Local User",
                "type": "user_message",
                "threadId": "thread-1",
                "parentId": None,
                "streaming": False,
                "waitForAnswer": None,
                "isError": False,
                "metadata": {},
                "tags": None,
                "input": "",
                "output": "Help me optimize for a data analyst role",
                "createdAt": "2026-04-14T08:00:00Z",
                "start": None,
                "end": None,
                "generation": None,
                "showInput": False,
                "defaultOpen": False,
                "autoCollapse": False,
                "language": None,
                "icon": None,
                "feedback": None,
            }
        )
        await self.data_layer.create_step(
            {
                "id": "step-assistant",
                "name": "AI Job Mediator",
                "type": "assistant_message",
                "threadId": "thread-1",
                "parentId": None,
                "streaming": False,
                "waitForAnswer": None,
                "isError": False,
                "metadata": {},
                "tags": None,
                "input": "",
                "output": "I can help with that.",
                "createdAt": "2026-04-14T08:00:10Z",
                "start": None,
                "end": None,
                "generation": None,
                "showInput": False,
                "defaultOpen": False,
                "autoCollapse": False,
                "language": None,
                "icon": None,
                "feedback": None,
            }
        )

        thread = await self.data_layer.get_thread("thread-1")
        assert thread is not None

        self.assertEqual(thread["metadata"]["resume_id"], "resume-123")
        self.assertEqual(thread["metadata"]["resume_status"], "ready")
        self.assertEqual(thread["metadata"]["tailored_resume_id"], "tailored-456")
        self.assertEqual(len(thread["steps"]), 2)
        self.assertEqual(
            thread["steps"][0]["output"],
            "Help me optimize for a data analyst role",
        )

        response = await self.data_layer.list_threads(
            pagination=Pagination(first=10),
            filters=ThreadFilter(userId=self.user.id),
        )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], "thread-1")
        self.assertEqual(response.data[0]["name"], "First message title")

    async def test_update_thread_empty_name_clears_upload_placeholder_title(self) -> None:
        await self.data_layer.update_thread(
            thread_id="thread-upload",
            name="sample_resume_with_edu.docx",
            user_id=self.user.id,
        )

        await self.data_layer.update_thread(
            thread_id="thread-upload",
            name="",
        )

        thread = await self.data_layer.get_thread("thread-upload")
        assert thread is not None
        self.assertIsNone(thread["name"])

    async def test_normalize_element_drops_none_fields(self) -> None:
        normalized = self.data_layer._normalize_element(
            {
                "id": "element-1",
                "threadId": "thread-1",
                "type": "file",
                "name": "resume.pdf",
                "url": "/public/chat-assets/thread-1/resume.pdf",
                "display": "inline",
                "mime": "application/pdf",
                "chainlitKey": None,
                "path": None,
                "objectKey": None,
                "page": None,
                "autoPlay": None,
                "playerConfig": None,
                "props": None,
            }
        )

        self.assertEqual(normalized["props"], {})
        self.assertNotIn("chainlitKey", normalized)
        self.assertNotIn("path", normalized)
        self.assertNotIn("objectKey", normalized)
        self.assertNotIn("page", normalized)


if __name__ == "__main__":
    unittest.main()
