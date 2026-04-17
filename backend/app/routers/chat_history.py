"""Frontend-facing chat history endpoints backed by TinyDB."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.chat_history import ChatHistoryStore
from app.database import db

router = APIRouter(prefix="/chat", tags=["Chat History"])
chat_store = ChatHistoryStore(db)


@router.post("/users")
async def create_user_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    identifier = (payload.get("identifier") or "").strip()
    if not identifier:
        raise HTTPException(status_code=400, detail="identifier is required")

    return chat_store.create_user(
        identifier=identifier,
        display_name=payload.get("display_name"),
        metadata=payload.get("metadata") or {},
    )


@router.get("/users/by-identifier/{identifier}")
async def get_user_endpoint(identifier: str) -> dict[str, Any]:
    user = chat_store.get_user(identifier)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.put("/threads/{thread_id}")
async def upsert_thread_endpoint(
    thread_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return chat_store.upsert_thread(
        thread_id,
        name=payload.get("name"),
        user_id=payload.get("user_id"),
        metadata=payload.get("metadata"),
        tags=payload.get("tags"),
    )


@router.get("/threads/{thread_id}")
async def get_thread_endpoint(thread_id: str) -> dict[str, Any]:
    thread = chat_store.get_thread(thread_id)
    if not thread:
        raise HTTPException(status_code=404, detail="Thread not found")
    return thread


@router.delete("/threads/{thread_id}")
async def delete_thread_endpoint(thread_id: str) -> dict[str, Any]:
    if not chat_store.delete_thread(thread_id):
        raise HTTPException(status_code=404, detail="Thread not found")
    return {"message": "Thread deleted successfully"}


@router.get("/threads")
async def list_threads_endpoint(
    user_id: str = Query(...),
    first: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    search: str | None = Query(None),
    feedback: int | None = Query(None),
) -> dict[str, Any]:
    return chat_store.list_threads(
        user_id=user_id,
        first=first,
        cursor=cursor,
        search=search,
        feedback=feedback,
    )


@router.post("/threads/{thread_id}/steps")
async def upsert_step_endpoint(
    thread_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return chat_store.upsert_step(thread_id, payload)


@router.delete("/steps/{step_id}")
async def delete_step_endpoint(step_id: str) -> dict[str, Any]:
    if not chat_store.delete_step(step_id):
        raise HTTPException(status_code=404, detail="Step not found")
    return {"message": "Step deleted successfully"}


@router.post("/threads/{thread_id}/elements")
async def upsert_element_endpoint(
    thread_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    return chat_store.upsert_element(thread_id, payload)


@router.get("/threads/{thread_id}/elements/{element_id}")
async def get_element_endpoint(thread_id: str, element_id: str) -> dict[str, Any]:
    element = chat_store.get_element(thread_id, element_id)
    if not element:
        raise HTTPException(status_code=404, detail="Element not found")
    return element


@router.delete("/elements/{element_id}")
async def delete_element_endpoint(
    element_id: str, thread_id: str | None = Query(None)
) -> dict[str, Any]:
    if not chat_store.delete_element(element_id, thread_id):
        raise HTTPException(status_code=404, detail="Element not found")
    return {"message": "Element deleted successfully"}


@router.post("/feedback")
async def upsert_feedback_endpoint(payload: dict[str, Any]) -> dict[str, Any]:
    if not payload.get("forId"):
        raise HTTPException(status_code=400, detail="forId is required")
    feedback_id = chat_store.upsert_feedback(payload)
    return {"id": feedback_id}


@router.delete("/feedback/{feedback_id}")
async def delete_feedback_endpoint(feedback_id: str) -> dict[str, Any]:
    if not chat_store.delete_feedback(feedback_id):
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"message": "Feedback deleted successfully"}


@router.get("/threads/{thread_id}/author")
async def get_thread_author_endpoint(thread_id: str) -> dict[str, Any]:
    try:
        author = chat_store.get_thread_author(thread_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"author": author}


@router.get("/favorites/{user_id}")
async def get_favorite_steps_endpoint(user_id: str) -> list[dict[str, Any]]:
    return chat_store.get_favorite_steps(user_id)
