import asyncio
import importlib.util
import shutil
import tempfile
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from chainlit.types import Pagination, ThreadFilter
from chainlit.user import User


FRONTEND_DIR = Path(__file__).resolve().parent
REMOTE_STORE_PATH = FRONTEND_DIR / "backend_chat_store.py"
LOCAL_STORE_PATH = FRONTEND_DIR / "local_chat_store.py"

if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class MockHTTPResponse:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.text = ""
        self.reason_phrase = ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class RecordingAsyncClient:
    requests = []
    responses = {}

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.get("timeout")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url, **kwargs):
        self.requests.append(("GET", url, kwargs))
        return self.responses[("GET", url)]

    async def post(self, url, **kwargs):
        self.requests.append(("POST", url, kwargs))
        return self.responses[("POST", url)]

    async def put(self, url, **kwargs):
        self.requests.append(("PUT", url, kwargs))
        return self.responses[("PUT", url)]

    async def delete(self, url, **kwargs):
        self.requests.append(("DELETE", url, kwargs))
        return self.responses[("DELETE", url)]


class BackendChatStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.remote_module = load_module("frontend_backend_store_module", REMOTE_STORE_PATH)
        self.local_module = load_module("frontend_local_store_module", LOCAL_STORE_PATH)
        RecordingAsyncClient.requests = []
        RecordingAsyncClient.responses = {}
        self.temp_dir = Path(tempfile.mkdtemp(prefix="backend-chat-store-"))

    async def asyncTearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    async def test_list_threads_returns_paginated_threads_from_backend(self):
        RecordingAsyncClient.responses = {
            (
                "GET",
                "http://backend/api/v1/chat/threads",
            ): MockHTTPResponse(
                {
                    "pageInfo": {
                        "hasNextPage": False,
                        "startCursor": "thread-1",
                        "endCursor": "thread-1",
                    },
                    "data": [
                        {
                            "id": "thread-1",
                            "createdAt": "2026-04-15T09:00:00Z",
                            "name": "Thread title",
                            "userId": "user-1",
                            "userIdentifier": "local-user",
                            "tags": [],
                            "metadata": {"resume_id": "master-123"},
                            "steps": [],
                            "elements": [],
                        }
                    ],
                }
            )
        }

        store = self.remote_module.BackendTinyDBDataLayer(
            base_url="http://backend",
            data_dir=self.temp_dir / "data",
            public_dir=self.temp_dir / "public",
        )

        with patch.object(self.remote_module.httpx, "AsyncClient", RecordingAsyncClient):
            response = await store.list_threads(
                pagination=Pagination(first=10),
                filters=ThreadFilter(userId="user-1"),
            )

        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], "thread-1")
        method, url, kwargs = RecordingAsyncClient.requests[-1]
        self.assertEqual((method, url), ("GET", "http://backend/api/v1/chat/threads"))
        self.assertEqual(
            kwargs["params"],
            {
                "user_id": "user-1",
                "first": 10,
            },
        )

    async def test_list_threads_omits_empty_optional_query_params(self):
        RecordingAsyncClient.responses = {
            (
                "GET",
                "http://backend/api/v1/chat/threads",
            ): MockHTTPResponse(
                {
                    "pageInfo": {
                        "hasNextPage": False,
                        "startCursor": None,
                        "endCursor": None,
                    },
                    "data": [],
                }
            )
        }

        store = self.remote_module.BackendTinyDBDataLayer(
            base_url="http://backend",
            data_dir=self.temp_dir / "data",
            public_dir=self.temp_dir / "public",
        )

        with patch.object(self.remote_module.httpx, "AsyncClient", RecordingAsyncClient):
            await store.list_threads(
                pagination=Pagination(first=35, cursor=""),
                filters=ThreadFilter(userId="user-1", search="", feedback=None),
            )

        _, _, kwargs = RecordingAsyncClient.requests[-1]
        self.assertEqual(
            kwargs["params"],
            {
                "user_id": "user-1",
                "first": 35,
            },
        )

    async def test_delete_thread_calls_backend_delete(self):
        RecordingAsyncClient.responses = {
            (
                "DELETE",
                "http://backend/api/v1/chat/threads/thread-1",
            ): MockHTTPResponse({"message": "deleted"})
        }

        store = self.remote_module.BackendTinyDBDataLayer(
            base_url="http://backend",
            data_dir=self.temp_dir / "data",
            public_dir=self.temp_dir / "public",
        )

        with patch.object(self.remote_module.httpx, "AsyncClient", RecordingAsyncClient):
            await store.delete_thread("thread-1")

        self.assertEqual(
            RecordingAsyncClient.requests[0][:2],
            ("DELETE", "http://backend/api/v1/chat/threads/thread-1"),
        )

    async def test_migrate_local_threads_if_needed_imports_legacy_threads(self):
        legacy_store = self.local_module.LocalJsonDataLayer(
            data_dir=self.temp_dir / "data",
            public_dir=self.temp_dir / "public",
        )
        user = await legacy_store.create_user(
            User(identifier="local-user", display_name="Local User")
        )
        assert user is not None
        await legacy_store.update_thread(
            thread_id="thread-legacy",
            name="Legacy thread",
            user_id=user.id,
            metadata={"resume_id": "master-123"},
        )
        await legacy_store.create_step(
            {
                "id": "step-legacy",
                "name": "Local User",
                "type": "user_message",
                "threadId": "thread-legacy",
                "parentId": None,
                "streaming": False,
                "waitForAnswer": None,
                "isError": False,
                "metadata": {},
                "tags": None,
                "input": "",
                "output": "Legacy content",
                "createdAt": "2026-04-15T09:00:00Z",
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

        RecordingAsyncClient.responses = {
            (
                "GET",
                "http://backend/api/v1/chat/threads",
            ): MockHTTPResponse(
                {
                    "pageInfo": {
                        "hasNextPage": False,
                        "startCursor": None,
                        "endCursor": None,
                    },
                    "data": [],
                }
            ),
            (
                "PUT",
                "http://backend/api/v1/chat/threads/thread-legacy",
            ): MockHTTPResponse({"id": "thread-legacy"}),
            (
                "POST",
                "http://backend/api/v1/chat/threads/thread-legacy/steps",
            ): MockHTTPResponse({"id": "step-legacy"}),
        }

        store = self.remote_module.BackendTinyDBDataLayer(
            base_url="http://backend",
            data_dir=self.temp_dir / "data",
            public_dir=self.temp_dir / "public",
        )

        with patch.object(self.remote_module.httpx, "AsyncClient", RecordingAsyncClient):
            await store.migrate_local_threads_if_needed(user_id="user-1")

        requested_urls = [(method, url) for method, url, _ in RecordingAsyncClient.requests]
        self.assertIn(("PUT", "http://backend/api/v1/chat/threads/thread-legacy"), requested_urls)
        self.assertIn(("POST", "http://backend/api/v1/chat/threads/thread-legacy/steps"), requested_urls)
        self.assertTrue(store.migration_marker.exists())

        await legacy_store.close()


if __name__ == "__main__":
    unittest.main()
