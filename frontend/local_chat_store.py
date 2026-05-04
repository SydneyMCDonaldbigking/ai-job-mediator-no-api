from __future__ import annotations

import asyncio
import json
import shutil
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chainlit.data.base import BaseDataLayer
from chainlit.types import Feedback, PageInfo, PaginatedResponse, Pagination, ThreadDict, ThreadFilter
from chainlit.user import PersistedUser, User

if TYPE_CHECKING:
    from chainlit.element import Element, ElementDict
    from chainlit.step import StepDict


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def safe_filename(name: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in name.strip())
    cleaned = cleaned.strip("._")
    return cleaned or "file"


def clip_thread_name(text: str | None, limit: int = 60) -> str | None:
    if not text:
        return None

    normalized = " ".join(text.split())
    if not normalized:
        return None

    if len(normalized) <= limit:
        return normalized

    return f"{normalized[: limit - 1].rstrip()}…"


class LocalJsonDataLayer(BaseDataLayer):
    def __init__(self, data_dir: Path, public_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.public_dir = Path(public_dir)
        self.chats_dir = self.data_dir / "chats"
        self.assets_dir = self.public_dir / "chat-assets"
        self.users_file = self.data_dir / "users.json"
        self._lock = asyncio.Lock()

        self.chats_dir.mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _thread_path(self, thread_id: str) -> Path:
        return self.chats_dir / f"{thread_id}.json"

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return deepcopy(default)

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return deepcopy(default)

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _load_users(self) -> list[dict[str, Any]]:
        return self._read_json(self.users_file, [])

    def _save_users(self, users: list[dict[str, Any]]) -> None:
        self._write_json(self.users_file, users)

    def _load_thread_record(self, thread_id: str) -> dict[str, Any] | None:
        path = self._thread_path(thread_id)
        if not path.exists():
            return None

        record = self._read_json(path, {})
        if not record:
            return None
        return record

    def _empty_thread_record(self, thread_id: str) -> dict[str, Any]:
        timestamp = utc_timestamp()
        return {
            "id": thread_id,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "name": None,
            "userId": None,
            "userIdentifier": None,
            "tags": [],
            "metadata": {},
            "steps": [],
            "elements": [],
        }

    def _save_thread_record(self, record: dict[str, Any]) -> None:
        record = deepcopy(record)
        record["updatedAt"] = record.get("updatedAt") or utc_timestamp()
        self._write_json(self._thread_path(record["id"]), record)

    def _thread_to_public(self, record: dict[str, Any]) -> ThreadDict:
        return ThreadDict(
            id=record["id"],
            createdAt=record.get("createdAt") or utc_timestamp(),
            name=record.get("name"),
            userId=record.get("userId"),
            userIdentifier=record.get("userIdentifier"),
            tags=record.get("tags") or [],
            metadata=record.get("metadata") or {},
            steps=record.get("steps") or [],
            elements=record.get("elements") or [],
        )

    def _all_thread_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for path in self.chats_dir.glob("*.json"):
            record = self._read_json(path, {})
            if record:
                records.append(record)
        return records

    def _find_user_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        for user in self._load_users():
            if user.get("identifier") == identifier:
                return user
        return None

    def _find_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        for user in self._load_users():
            if user.get("id") == user_id:
                return user
        return None

    def _persist_element_asset(self, element: "Element") -> str | None:
        if element.url:
            return element.url

        element_name = safe_filename(element.name or f"{element.id}.bin")
        destination = self.assets_dir / element.thread_id / f"{element.id}_{element_name}"
        destination.parent.mkdir(parents=True, exist_ok=True)

        if element.path:
            shutil.copyfile(element.path, destination)
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

    def _merge_metadata(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = deepcopy(existing)
        if not incoming:
            return merged

        for key, value in incoming.items():
            if value is None:
                merged.pop(key, None)
            else:
                merged[key] = value
        return merged

    def _normalize_step(self, step_dict: "StepDict") -> "StepDict":
        normalized = dict(step_dict)
        normalized["threadId"] = normalized.get("threadId", "")
        normalized["metadata"] = normalized.get("metadata") or {}
        normalized["input"] = normalized.get("input") or ""
        normalized["output"] = normalized.get("output") or ""
        normalized["streaming"] = bool(normalized.get("streaming", False))
        normalized["createdAt"] = normalized.get("createdAt") or utc_timestamp()
        normalized["showInput"] = normalized.get("showInput", False)
        normalized["defaultOpen"] = normalized.get("defaultOpen", False)
        normalized["autoCollapse"] = normalized.get("autoCollapse", False)
        return normalized  # type: ignore[return-value]

    def _normalize_element(self, element_dict: "ElementDict") -> "ElementDict":
        normalized = dict(element_dict)
        normalized["props"] = normalized.get("props") or {}
        cleaned = {
            key: value
            for key, value in normalized.items()
            if value is not None or key in {"props"}
        }
        return cleaned  # type: ignore[return-value]

    async def get_user(self, identifier: str) -> PersistedUser | None:
        user = self._find_user_by_identifier(identifier)
        if not user:
            return None

        return PersistedUser(
            id=user["id"],
            createdAt=user["createdAt"],
            identifier=user["identifier"],
            display_name=user.get("display_name"),
            metadata=user.get("metadata") or {},
        )

    async def create_user(self, user: User) -> PersistedUser | None:
        async with self._lock:
            users = self._load_users()
            existing = next(
                (item for item in users if item.get("identifier") == user.identifier),
                None,
            )

            if existing:
                existing["display_name"] = user.display_name
                existing["metadata"] = user.metadata or {}
                self._save_users(users)
                return PersistedUser(
                    id=existing["id"],
                    createdAt=existing["createdAt"],
                    identifier=existing["identifier"],
                    display_name=existing.get("display_name"),
                    metadata=existing.get("metadata") or {},
                )

            record = {
                "id": str(uuid.uuid4()),
                "createdAt": utc_timestamp(),
                "identifier": user.identifier,
                "display_name": user.display_name,
                "metadata": user.metadata or {},
            }
            users.append(record)
            self._save_users(users)

        return PersistedUser(
            id=record["id"],
            createdAt=record["createdAt"],
            identifier=record["identifier"],
            display_name=record.get("display_name"),
            metadata=record.get("metadata") or {},
        )

    async def delete_feedback(self, feedback_id: str) -> bool:
        async with self._lock:
            for record in self._all_thread_records():
                updated = False
                for step in record.get("steps", []):
                    feedback = step.get("feedback")
                    if feedback and feedback.get("id") == feedback_id:
                        step["feedback"] = None
                        updated = True
                if updated:
                    self._save_thread_record(record)
        return True

    async def upsert_feedback(self, feedback: Feedback) -> str:
        feedback_id = feedback.id or str(uuid.uuid4())
        async with self._lock:
            for record in self._all_thread_records():
                updated = False
                for step in record.get("steps", []):
                    if step.get("id") == feedback.forId:
                        step["feedback"] = {
                            "forId": feedback.forId,
                            "id": feedback_id,
                            "value": feedback.value,
                            "comment": feedback.comment,
                        }
                        updated = True
                        break
                if updated:
                    record["updatedAt"] = utc_timestamp()
                    self._save_thread_record(record)
                    return feedback_id
        return feedback_id

    async def create_element(self, element: "Element") -> None:
        async with self._lock:
            record = self._load_thread_record(element.thread_id) or self._empty_thread_record(element.thread_id)
            elements = record.get("elements") or []

            element_dict = self._normalize_element(element.to_dict())
            element_dict["threadId"] = element.thread_id
            persisted_url = self._persist_element_asset(element)
            if persisted_url:
                element_dict["url"] = persisted_url
                element_dict["chainlitKey"] = None

            existing_index = next(
                (index for index, item in enumerate(elements) if item.get("id") == element.id),
                None,
            )
            if existing_index is None:
                elements.append(element_dict)
            else:
                elements[existing_index] = element_dict

            record["elements"] = elements
            record["updatedAt"] = utc_timestamp()
            self._save_thread_record(record)

    async def get_element(self, thread_id: str, element_id: str) -> "ElementDict" | None:
        record = self._load_thread_record(thread_id)
        if not record:
            return None

        for element in record.get("elements", []):
            if element.get("id") == element_id:
                return element  # type: ignore[return-value]
        return None

    async def delete_element(self, element_id: str, thread_id: str | None = None) -> None:
        async with self._lock:
            records = (
                [self._load_thread_record(thread_id)] if thread_id else self._all_thread_records()
            )
            for record in records:
                if not record:
                    continue
                original_elements = record.get("elements") or []
                remaining = []
                removed = False
                for element in original_elements:
                    if element.get("id") == element_id:
                        self._remove_element_asset(element.get("url"))
                        removed = True
                        continue
                    remaining.append(element)
                if removed:
                    record["elements"] = remaining
                    record["updatedAt"] = utc_timestamp()
                    self._save_thread_record(record)

    async def create_step(self, step_dict: "StepDict") -> None:
        await self.update_step(step_dict)

    async def update_step(self, step_dict: "StepDict") -> None:
        normalized = self._normalize_step(step_dict)
        thread_id = normalized["threadId"]
        async with self._lock:
            record = self._load_thread_record(thread_id) or self._empty_thread_record(thread_id)
            steps = record.get("steps") or []

            existing_index = next(
                (index for index, item in enumerate(steps) if item.get("id") == normalized["id"]),
                None,
            )
            if existing_index is None:
                steps.append(normalized)
            else:
                steps[existing_index] = normalized

            steps.sort(key=lambda item: item.get("createdAt") or "")
            record["steps"] = steps
            record["updatedAt"] = normalized.get("createdAt") or utc_timestamp()

            if not record.get("name") and normalized.get("type") == "user_message":
                record["name"] = clip_thread_name(normalized.get("output") or normalized.get("input"))

            self._save_thread_record(record)

    async def delete_step(self, step_id: str) -> None:
        async with self._lock:
            for record in self._all_thread_records():
                original_steps = record.get("steps") or []
                remaining_steps = [step for step in original_steps if step.get("id") != step_id]
                if len(remaining_steps) == len(original_steps):
                    continue

                remaining_elements = [
                    element for element in record.get("elements", []) if element.get("forId") != step_id
                ]
                for element in record.get("elements", []):
                    if element.get("forId") == step_id:
                        self._remove_element_asset(element.get("url"))

                record["steps"] = remaining_steps
                record["elements"] = remaining_elements
                record["updatedAt"] = utc_timestamp()
                self._save_thread_record(record)

    async def get_thread_author(self, thread_id: str) -> str:
        record = self._load_thread_record(thread_id)
        if not record or not record.get("userIdentifier"):
            raise ValueError(f"Author not found for thread_id {thread_id}")
        return record["userIdentifier"]

    async def delete_thread(self, thread_id: str) -> None:
        async with self._lock:
            record = self._load_thread_record(thread_id)
            if record:
                for element in record.get("elements", []):
                    self._remove_element_asset(element.get("url"))

            thread_path = self._thread_path(thread_id)
            if thread_path.exists():
                thread_path.unlink()

            thread_asset_dir = self.assets_dir / thread_id
            if thread_asset_dir.exists():
                shutil.rmtree(thread_asset_dir)

    async def list_threads(
        self,
        pagination: Pagination,
        filters: ThreadFilter,
    ) -> PaginatedResponse[ThreadDict]:
        if not filters.userId:
            raise ValueError("userId is required")

        records = [
            record
            for record in self._all_thread_records()
            if record.get("userId") == filters.userId
        ]

        search = (filters.search or "").strip().casefold()
        if search:
            filtered_records = []
            for record in records:
                haystacks = [
                    record.get("name") or "",
                    *(step.get("input") or "" for step in record.get("steps", [])),
                    *(step.get("output") or "" for step in record.get("steps", [])),
                ]
                if any(search in haystack.casefold() for haystack in haystacks):
                    filtered_records.append(record)
            records = filtered_records

        if filters.feedback is not None:
            expected_value = int(filters.feedback)
            records = [
                record
                for record in records
                if any(
                    step.get("feedback") and step["feedback"].get("value") == expected_value
                    for step in record.get("steps", [])
                )
            ]

        records.sort(
            key=lambda record: record.get("updatedAt") or record.get("createdAt") or "",
            reverse=True,
        )

        start_index = 0
        if pagination.cursor:
            for index, record in enumerate(records):
                if record.get("id") == pagination.cursor:
                    start_index = index + 1
                    break

        page_records = records[start_index : start_index + pagination.first]
        public_threads = [self._thread_to_public(record) for record in page_records]

        return PaginatedResponse(
            pageInfo=PageInfo(
                hasNextPage=start_index + pagination.first < len(records),
                startCursor=public_threads[0]["id"] if public_threads else None,
                endCursor=public_threads[-1]["id"] if public_threads else None,
            ),
            data=public_threads,
        )

    async def get_thread(self, thread_id: str) -> ThreadDict | None:
        record = self._load_thread_record(thread_id)
        if not record:
            return None
        return self._thread_to_public(record)

    async def update_thread(
        self,
        thread_id: str,
        name: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> None:
        async with self._lock:
            record = self._load_thread_record(thread_id) or self._empty_thread_record(thread_id)

            if user_id is not None:
                record["userId"] = user_id
                persisted_user = self._find_user_by_id(user_id)
                record["userIdentifier"] = (
                    persisted_user.get("identifier") if persisted_user else record.get("userIdentifier")
                )

            if name is not None:
                record["name"] = clip_thread_name(name)

            if tags is not None:
                record["tags"] = tags

            record["metadata"] = self._merge_metadata(record.get("metadata") or {}, metadata)
            record["updatedAt"] = utc_timestamp()

            self._save_thread_record(record)

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        return None

    async def get_favorite_steps(self, user_id: str) -> list["StepDict"]:
        favorite_steps: list["StepDict"] = []
        for record in self._all_thread_records():
            if record.get("userId") != user_id:
                continue
            for step in record.get("steps", []):
                metadata = step.get("metadata") or {}
                if metadata.get("favorite"):
                    favorite_steps.append(step)
        favorite_steps.sort(key=lambda step: step.get("createdAt") or "", reverse=True)
        return favorite_steps
