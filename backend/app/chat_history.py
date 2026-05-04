"""TinyDB-backed chat history store for the Chainlit frontend."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from tinydb import Query

from app.database import Database


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def clip_thread_name(text: str | None, limit: int = 60) -> str | None:
    if not text:
        return None

    normalized = " ".join(text.split())
    if not normalized:
        return None

    if len(normalized) <= limit:
        return normalized

    return f"{normalized[: limit - 3].rstrip()}..."


class ChatHistoryStore:
    """Persistence helper mirroring the frontend Chainlit data-layer shape."""

    def __init__(self, database: Database) -> None:
        self.database = database

    @property
    def users(self):
        return self.database.db.table("chat_users")

    @property
    def threads(self):
        return self.database.db.table("chat_threads")

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

    def _get_user_by_identifier(self, identifier: str) -> dict[str, Any] | None:
        user_query = Query()
        results = self.users.search(user_query.identifier == identifier)
        return results[0] if results else None

    def _get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        user_query = Query()
        results = self.users.search(user_query.id == user_id)
        return results[0] if results else None

    def get_user(self, identifier: str) -> dict[str, Any] | None:
        user = self._get_user_by_identifier(identifier)
        return deepcopy(user) if user else None

    def create_user(
        self,
        identifier: str,
        display_name: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        existing = self._get_user_by_identifier(identifier)
        if existing:
            updates = {
                "display_name": display_name,
                "metadata": metadata or {},
            }
            user_query = Query()
            self.users.update(updates, user_query.id == existing["id"])
            existing.update(updates)
            return deepcopy(existing)

        record = {
            "id": str(uuid4()),
            "createdAt": utc_timestamp(),
            "identifier": identifier,
            "display_name": display_name,
            "metadata": metadata or {},
        }
        self.users.insert(record)
        return deepcopy(record)

    def _get_thread_record(self, thread_id: str) -> dict[str, Any] | None:
        thread_query = Query()
        results = self.threads.search(thread_query.id == thread_id)
        return results[0] if results else None

    def _save_thread_record(self, record: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(record)
        payload["updatedAt"] = payload.get("updatedAt") or utc_timestamp()
        thread_query = Query()
        existing = self._get_thread_record(payload["id"])
        if existing:
            self.threads.update(payload, thread_query.id == payload["id"])
        else:
            self.threads.insert(payload)
        return deepcopy(payload)

    def upsert_thread(
        self,
        thread_id: str,
        *,
        name: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        record = self._get_thread_record(thread_id) or self._empty_thread_record(thread_id)

        if user_id is not None:
            record["userId"] = user_id
            persisted_user = self._get_user_by_id(user_id)
            record["userIdentifier"] = (
                persisted_user.get("identifier") if persisted_user else record.get("userIdentifier")
            )

        if name is not None:
            record["name"] = clip_thread_name(name)

        if tags is not None:
            record["tags"] = tags

        if metadata:
            merged = deepcopy(record.get("metadata") or {})
            for key, value in metadata.items():
                if value is None:
                    merged.pop(key, None)
                else:
                    merged[key] = value
            record["metadata"] = merged

        record["updatedAt"] = utc_timestamp()
        return self._save_thread_record(record)

    def get_thread(self, thread_id: str) -> dict[str, Any] | None:
        record = self._get_thread_record(thread_id)
        return deepcopy(record) if record else None

    def _normalize_step(self, step_dict: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(step_dict)
        normalized["threadId"] = normalized.get("threadId") or ""
        normalized["metadata"] = normalized.get("metadata") or {}
        normalized["input"] = normalized.get("input") or ""
        normalized["output"] = normalized.get("output") or ""
        normalized["streaming"] = bool(normalized.get("streaming", False))
        normalized["createdAt"] = normalized.get("createdAt") or utc_timestamp()
        normalized["showInput"] = normalized.get("showInput", False)
        normalized["defaultOpen"] = normalized.get("defaultOpen", False)
        normalized["autoCollapse"] = normalized.get("autoCollapse", False)
        return normalized

    def upsert_step(self, thread_id: str, step_dict: dict[str, Any]) -> dict[str, Any]:
        record = self._get_thread_record(thread_id) or self._empty_thread_record(thread_id)
        normalized = self._normalize_step(step_dict)
        normalized["threadId"] = thread_id
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
        return deepcopy(normalized)

    def delete_step(self, step_id: str) -> bool:
        removed = False
        for record in self.threads.all():
            original_steps = record.get("steps") or []
            remaining_steps = [step for step in original_steps if step.get("id") != step_id]
            if len(remaining_steps) == len(original_steps):
                continue

            remaining_elements = [
                element for element in record.get("elements", []) if element.get("forId") != step_id
            ]
            record["steps"] = remaining_steps
            record["elements"] = remaining_elements
            record["updatedAt"] = utc_timestamp()
            self._save_thread_record(record)
            removed = True
        return removed

    def _normalize_element(self, element_dict: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(element_dict)
        normalized["path"] = None
        normalized["objectKey"] = None
        normalized["props"] = normalized.get("props") or {}
        return normalized

    def upsert_element(self, thread_id: str, element_dict: dict[str, Any]) -> dict[str, Any]:
        record = self._get_thread_record(thread_id) or self._empty_thread_record(thread_id)
        normalized = self._normalize_element(element_dict)
        normalized["threadId"] = thread_id
        elements = record.get("elements") or []

        existing_index = next(
            (index for index, item in enumerate(elements) if item.get("id") == normalized["id"]),
            None,
        )
        if existing_index is None:
            elements.append(normalized)
        else:
            elements[existing_index] = normalized

        record["elements"] = elements
        record["updatedAt"] = utc_timestamp()
        self._save_thread_record(record)
        return deepcopy(normalized)

    def get_element(self, thread_id: str, element_id: str) -> dict[str, Any] | None:
        record = self._get_thread_record(thread_id)
        if not record:
            return None

        for element in record.get("elements", []):
            if element.get("id") == element_id:
                return deepcopy(element)
        return None

    def delete_element(self, element_id: str, thread_id: str | None = None) -> bool:
        removed = False
        records = (
            [self._get_thread_record(thread_id)] if thread_id else self.threads.all()
        )
        for record in records:
            if not record:
                continue
            original_elements = record.get("elements") or []
            remaining = [item for item in original_elements if item.get("id") != element_id]
            if len(remaining) == len(original_elements):
                continue

            record["elements"] = remaining
            record["updatedAt"] = utc_timestamp()
            self._save_thread_record(record)
            removed = True
        return removed

    def upsert_feedback(self, feedback: dict[str, Any]) -> str:
        feedback_id = feedback.get("id") or str(uuid4())
        for record in self.threads.all():
            updated = False
            for step in record.get("steps", []):
                if step.get("id") == feedback.get("forId"):
                    step["feedback"] = {
                        "forId": feedback.get("forId"),
                        "id": feedback_id,
                        "value": feedback.get("value"),
                        "comment": feedback.get("comment"),
                    }
                    updated = True
                    break
            if updated:
                record["updatedAt"] = utc_timestamp()
                self._save_thread_record(record)
                return feedback_id
        return feedback_id

    def delete_feedback(self, feedback_id: str) -> bool:
        removed = False
        for record in self.threads.all():
            updated = False
            for step in record.get("steps", []):
                feedback = step.get("feedback")
                if feedback and feedback.get("id") == feedback_id:
                    step["feedback"] = None
                    updated = True
            if updated:
                record["updatedAt"] = utc_timestamp()
                self._save_thread_record(record)
                removed = True
        return removed

    def get_thread_author(self, thread_id: str) -> str:
        record = self._get_thread_record(thread_id)
        if not record or not record.get("userIdentifier"):
            raise ValueError(f"Author not found for thread_id {thread_id}")
        return str(record["userIdentifier"])

    def delete_thread(self, thread_id: str) -> bool:
        thread_query = Query()
        removed = self.threads.remove(thread_query.id == thread_id)
        return len(removed) > 0

    def list_threads(
        self,
        *,
        user_id: str,
        first: int = 20,
        cursor: str | None = None,
        search: str | None = None,
        feedback: int | None = None,
    ) -> dict[str, Any]:
        records = [
            deepcopy(record)
            for record in self.threads.all()
            if record.get("userId") == user_id
        ]

        normalized_search = (search or "").strip().casefold()
        if normalized_search:
            filtered_records = []
            for record in records:
                haystacks = [
                    record.get("name") or "",
                    *(step.get("input") or "" for step in record.get("steps", [])),
                    *(step.get("output") or "" for step in record.get("steps", [])),
                ]
                if any(normalized_search in haystack.casefold() for haystack in haystacks):
                    filtered_records.append(record)
            records = filtered_records

        if feedback is not None:
            records = [
                record
                for record in records
                if any(
                    step.get("feedback") and step["feedback"].get("value") == feedback
                    for step in record.get("steps", [])
                )
            ]

        records.sort(
            key=lambda record: record.get("updatedAt") or record.get("createdAt") or "",
            reverse=True,
        )

        start_index = 0
        if cursor:
            for index, record in enumerate(records):
                if record.get("id") == cursor:
                    start_index = index + 1
                    break

        page_records = records[start_index : start_index + first]
        return {
            "pageInfo": {
                "hasNextPage": start_index + first < len(records),
                "startCursor": page_records[0]["id"] if page_records else None,
                "endCursor": page_records[-1]["id"] if page_records else None,
            },
            "data": page_records,
        }

    def get_favorite_steps(self, user_id: str) -> list[dict[str, Any]]:
        favorite_steps: list[dict[str, Any]] = []
        for record in self.threads.all():
            if record.get("userId") != user_id:
                continue
            for step in record.get("steps", []):
                metadata = step.get("metadata") or {}
                if metadata.get("favorite"):
                    favorite_steps.append(deepcopy(step))
        favorite_steps.sort(key=lambda step: step.get("createdAt") or "", reverse=True)
        return favorite_steps
