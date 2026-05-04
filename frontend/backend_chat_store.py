from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
from chainlit.data.base import BaseDataLayer
from chainlit.types import Feedback, PageInfo, PaginatedResponse, Pagination, ThreadDict, ThreadFilter
from chainlit.user import PersistedUser, User

from local_chat_store import LocalJsonDataLayer, safe_filename

if TYPE_CHECKING:
    from chainlit.element import Element, ElementDict
    from chainlit.step import StepDict


class BackendTinyDBDataLayer(BaseDataLayer):
    """Chainlit data layer that stores metadata in backend TinyDB."""

    def __init__(self, base_url: str, data_dir: Path, public_dir: Path) -> None:
        self.base_url = base_url.rstrip("/")
        self.data_dir = Path(data_dir)
        self.public_dir = Path(public_dir)
        self.assets_dir = self.public_dir / "chat-assets"
        self.migration_marker = self.data_dir / ".chat_history_migrated"
        self._migration_lock = asyncio.Lock()

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.public_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)

        self.legacy_store = LocalJsonDataLayer(
            data_dir=self.data_dir,
            public_dir=self.public_dir,
        )

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async with httpx.AsyncClient(timeout=60.0) as client:
            url = f"{self.base_url}{path}"
            method = method.upper()
            if method == "GET":
                return await client.get(url, **kwargs)
            if method == "POST":
                return await client.post(url, **kwargs)
            if method == "PUT":
                return await client.put(url, **kwargs)
            if method == "DELETE":
                return await client.delete(url, **kwargs)
            return await client.request(method, url, **kwargs)

    async def _request_json(self, method: str, path: str, **kwargs) -> Any:
        response = await self._request(method, path, **kwargs)
        response.raise_for_status()
        return response.json()

    def _persist_element_asset(self, element: "Element") -> str | None:
        if element.url:
            return element.url

        element_name = safe_filename(element.name or f"{element.id}.bin")
        destination = self.assets_dir / element.thread_id / f"{element.id}_{element_name}"
        destination.parent.mkdir(parents=True, exist_ok=True)

        if element.path:
            destination.write_bytes(Path(element.path).read_bytes())
        elif element.content is not None:
            payload = (
                element.content.encode("utf-8")
                if isinstance(element.content, str)
                else bytes(element.content)
            )
            destination.write_bytes(payload)
        else:
            return None

        relative_path = destination.relative_to(self.public_dir).as_posix()
        return f"/public/{relative_path}"

    def _remove_element_asset(self, url: str | None) -> None:
        if not url or not url.startswith("/public/"):
            return

        relative = url.removeprefix("/public/")
        asset_path = self.public_dir / Path(relative)
        if asset_path.exists():
            asset_path.unlink()

    async def get_user(self, identifier: str) -> PersistedUser | None:
        response = await self._request(
            "GET",
            f"/api/v1/chat/users/by-identifier/{identifier}",
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        user = response.json()
        return PersistedUser(
            id=user["id"],
            createdAt=user["createdAt"],
            identifier=user["identifier"],
            display_name=user.get("display_name"),
            metadata=user.get("metadata") or {},
        )

    async def create_user(self, user: User) -> PersistedUser | None:
        payload = await self._request_json(
            "POST",
            "/api/v1/chat/users",
            json={
                "identifier": user.identifier,
                "display_name": user.display_name,
                "metadata": user.metadata or {},
            },
        )
        return PersistedUser(
            id=payload["id"],
            createdAt=payload["createdAt"],
            identifier=payload["identifier"],
            display_name=payload.get("display_name"),
            metadata=payload.get("metadata") or {},
        )

    async def delete_feedback(self, feedback_id: str) -> bool:
        response = await self._request(
            "DELETE",
            f"/api/v1/chat/feedback/{feedback_id}",
        )
        if response.status_code == 404:
            return False
        response.raise_for_status()
        return True

    async def upsert_feedback(self, feedback: Feedback) -> str:
        payload = await self._request_json(
            "POST",
            "/api/v1/chat/feedback",
            json={
                "forId": feedback.forId,
                "id": feedback.id,
                "value": feedback.value,
                "comment": feedback.comment,
            },
        )
        return payload["id"]

    async def create_element(self, element: "Element") -> None:
        payload = dict(element.to_dict())
        payload["threadId"] = element.thread_id
        payload["props"] = payload.get("props") or {}
        persisted_url = self._persist_element_asset(element)
        if persisted_url:
            payload["url"] = persisted_url
        payload = {
            key: value
            for key, value in payload.items()
            if value is not None or key in {"props"}
        }

        await self._request_json(
            "POST",
            f"/api/v1/chat/threads/{element.thread_id}/elements",
            json=payload,
        )

    async def get_element(self, thread_id: str, element_id: str) -> "ElementDict" | None:
        response = await self._request(
            "GET",
            f"/api/v1/chat/threads/{thread_id}/elements/{element_id}",
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()  # type: ignore[return-value]

    async def delete_element(self, element_id: str, thread_id: str | None = None) -> None:
        if thread_id:
            element = await self.get_element(thread_id, element_id)
            if element:
                self._remove_element_asset(element.get("url"))

        response = await self._request(
            "DELETE",
            f"/api/v1/chat/elements/{element_id}",
            params={"thread_id": thread_id} if thread_id else None,
        )
        if response.status_code not in (200, 404):
            response.raise_for_status()

    async def create_step(self, step_dict: "StepDict") -> None:
        await self.update_step(step_dict)

    async def update_step(self, step_dict: "StepDict") -> None:
        thread_id = step_dict.get("threadId", "")
        await self._request_json(
            "POST",
            f"/api/v1/chat/threads/{thread_id}/steps",
            json=dict(step_dict),
        )

    async def delete_step(self, step_id: str) -> None:
        response = await self._request(
            "DELETE",
            f"/api/v1/chat/steps/{step_id}",
        )
        if response.status_code not in (200, 404):
            response.raise_for_status()

    async def get_thread_author(self, thread_id: str) -> str:
        payload = await self._request_json(
            "GET",
            f"/api/v1/chat/threads/{thread_id}/author",
        )
        return payload["author"]

    async def delete_thread(self, thread_id: str) -> None:
        response = await self._request(
            "DELETE",
            f"/api/v1/chat/threads/{thread_id}",
        )
        if response.status_code not in (200, 404):
            response.raise_for_status()

    async def migrate_local_threads_if_needed(self, user_id: str) -> None:
        if self.migration_marker.exists():
            return

        async with self._migration_lock:
            if self.migration_marker.exists():
                return

            existing = await self._request_json(
                "GET",
                "/api/v1/chat/threads",
                params={"user_id": user_id, "first": 1},
            )
            if existing.get("data"):
                self.migration_marker.write_text("migrated", encoding="utf-8")
                return

            legacy_records = self.legacy_store._all_thread_records()
            if not legacy_records:
                self.migration_marker.write_text("migrated", encoding="utf-8")
                return

            for record in legacy_records:
                await self.update_thread(
                    thread_id=record["id"],
                    name=record.get("name"),
                    user_id=user_id,
                    metadata=record.get("metadata"),
                    tags=record.get("tags"),
                )

                for step in record.get("steps", []):
                    await self.update_step(step)

                for element in record.get("elements", []):
                    await self._request_json(
                        "POST",
                        f"/api/v1/chat/threads/{record['id']}/elements",
                        json=element,
                    )

            self.migration_marker.write_text("migrated", encoding="utf-8")

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        if not filters.userId:
            raise ValueError("userId is required")

        await self.migrate_local_threads_if_needed(filters.userId)

        params: dict[str, Any] = {
            "user_id": filters.userId,
            "first": pagination.first,
        }
        if pagination.cursor:
            params["cursor"] = pagination.cursor
        if filters.search:
            params["search"] = filters.search
        if filters.feedback is not None:
            params["feedback"] = filters.feedback

        payload = await self._request_json(
            "GET",
            "/api/v1/chat/threads",
            params=params,
        )

        page_info = payload.get("pageInfo") or {}
        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=page_info.get("hasNextPage", False),
                startCursor=page_info.get("startCursor"),
                endCursor=page_info.get("endCursor"),
            ),
            data=payload.get("data") or [],
        )

    async def get_thread(self, thread_id: str) -> ThreadDict | None:
        response = await self._request(
            "GET",
            f"/api/v1/chat/threads/{thread_id}",
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def update_thread(
        self,
        thread_id: str,
        name: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        await self._request_json(
            "PUT",
            f"/api/v1/chat/threads/{thread_id}",
            json={
                "name": name,
                "user_id": user_id,
                "metadata": metadata,
                "tags": tags,
            },
        )

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        await self.legacy_store.close()

    async def get_favorite_steps(self, user_id: str) -> list["StepDict"]:
        payload = await self._request_json(
            "GET",
            f"/api/v1/chat/favorites/{user_id}",
        )
        return payload
