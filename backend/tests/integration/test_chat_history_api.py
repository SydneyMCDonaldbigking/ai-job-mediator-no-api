"""Integration tests for backend chat history endpoints."""

from httpx import ASGITransport, AsyncClient
import pytest

from app.database import db
from app.main import app


@pytest.fixture(autouse=True)
def reset_chat_tables():
    db.db.table("chat_users").truncate()
    db.db.table("chat_threads").truncate()
    yield
    db.db.table("chat_users").truncate()
    db.db.table("chat_threads").truncate()


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


class TestChatUsersAndThreads:
    async def test_chat_thread_round_trip(self, client):
        async with client:
            user_resp = await client.post(
                "/api/v1/chat/users",
                json={
                    "identifier": "local-user",
                    "display_name": "Local User",
                    "metadata": {"role": "local-user"},
                },
            )
            assert user_resp.status_code == 200
            user_id = user_resp.json()["id"]

            upsert_resp = await client.put(
                "/api/v1/chat/threads/thread-1",
                json={
                    "name": "Backend role thread",
                    "user_id": user_id,
                    "metadata": {"resume_id": "master-123"},
                    "tags": ["career-ops"],
                },
            )
            assert upsert_resp.status_code == 200

            step_resp = await client.post(
                "/api/v1/chat/threads/thread-1/steps",
                json={
                    "id": "step-1",
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
                    "output": "Please evaluate this backend role.",
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
                },
            )
            assert step_resp.status_code == 200

            thread_resp = await client.get("/api/v1/chat/threads/thread-1")
            assert thread_resp.status_code == 200
            thread = thread_resp.json()
            assert thread["metadata"]["resume_id"] == "master-123"
            assert len(thread["steps"]) == 1
            assert thread["steps"][0]["output"] == "Please evaluate this backend role."

            list_resp = await client.get(
                "/api/v1/chat/threads",
                params={"user_id": user_id, "first": 10},
            )
            assert list_resp.status_code == 200
            listing = list_resp.json()
            assert listing["pageInfo"]["hasNextPage"] is False
            assert listing["data"][0]["id"] == "thread-1"

    async def test_delete_thread_removes_it_from_history(self, client):
        async with client:
            user_resp = await client.post(
                "/api/v1/chat/users",
                json={
                    "identifier": "local-user",
                    "display_name": "Local User",
                    "metadata": {},
                },
            )
            user_id = user_resp.json()["id"]

            await client.put(
                "/api/v1/chat/threads/thread-delete",
                json={
                    "name": "Delete me",
                    "user_id": user_id,
                    "metadata": {},
                    "tags": [],
                },
            )

            delete_resp = await client.delete("/api/v1/chat/threads/thread-delete")
            assert delete_resp.status_code == 200

            get_resp = await client.get("/api/v1/chat/threads/thread-delete")
            assert get_resp.status_code == 404
