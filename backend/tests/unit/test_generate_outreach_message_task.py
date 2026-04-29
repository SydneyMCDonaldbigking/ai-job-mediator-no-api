import asyncio
import importlib

import pytest

from app.ai.tasks.generate_outreach_message import (
    OutreachMessageRunnableInput,
    build_generate_outreach_message_runnable,
    generate_outreach_message_text,
)
from app.services import cover_letter as cover_letter_service_module

outreach_message_task_module = importlib.import_module(
    "app.ai.tasks.generate_outreach_message"
)


def test_build_generate_outreach_message_runnable_returns_ainvokable_pipeline():
    runnable = build_generate_outreach_message_runnable()
    assert hasattr(runnable, "ainvoke")


def test_generate_outreach_message_text_uses_langchain_runnable(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: OutreachMessageRunnableInput) -> str:
            assert task_input.language == "en"
            assert "Stripe" in task_input.job_description
            assert "Python" in str(task_input.resume_data)
            return "  Tailored outreach message body.  "

    monkeypatch.setattr(
        outreach_message_task_module,
        "build_generate_outreach_message_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_outreach_message_text(
            resume_data={
                "summary": "Python backend engineer",
                "skills": ["Python", "FastAPI"],
            },
            job_description="Stripe is hiring a Senior FastAPI engineer role",
            language="en",
        )
    )

    assert result == "Tailored outreach message body."


def test_generate_outreach_message_text_normalizes_surrounding_whitespace(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: OutreachMessageRunnableInput) -> str:
            return "\n  Short outreach note.  \n"

    monkeypatch.setattr(
        outreach_message_task_module,
        "build_generate_outreach_message_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_outreach_message_text(
            resume_data={"summary": "Python backend engineer"},
            job_description="FastAPI platform role",
            language="en",
        )
    )

    assert result == "Short outreach note."


def test_generate_outreach_message_text_propagates_task_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: OutreachMessageRunnableInput) -> str:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        outreach_message_task_module,
        "build_generate_outreach_message_runnable",
        lambda: FakeRunnable(),
    )

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        asyncio.run(
            generate_outreach_message_text(
                resume_data={"summary": "Python backend engineer"},
                job_description="Senior FastAPI engineer role",
                language="en",
            )
        )


def test_generate_outreach_message_service_delegates_to_ai_task(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_generate_outreach_message_text(**kwargs) -> str:
        assert kwargs["language"] == "ja"
        assert "Stripe" in kwargs["job_description"]
        return "Delegated outreach message"

    monkeypatch.setattr(
        cover_letter_service_module,
        "generate_outreach_message_text",
        fake_generate_outreach_message_text,
    )

    result = asyncio.run(
        cover_letter_service_module.generate_outreach_message(
            resume_data={"summary": "Python backend engineer"},
            job_description="Stripe is hiring a Senior FastAPI engineer role",
            language="ja",
        )
    )

    assert result == "Delegated outreach message"
