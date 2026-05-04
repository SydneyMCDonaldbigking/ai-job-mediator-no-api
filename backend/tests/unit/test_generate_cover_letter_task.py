import asyncio
import importlib

import pytest

from app.ai.tasks.generate_cover_letter import (
    CoverLetterRunnableInput,
    build_generate_cover_letter_runnable,
    generate_cover_letter_text,
)
from app.services import cover_letter as cover_letter_service_module

cover_letter_task_module = importlib.import_module("app.ai.tasks.generate_cover_letter")


def test_build_generate_cover_letter_runnable_returns_ainvokable_pipeline():
    runnable = build_generate_cover_letter_runnable()
    assert hasattr(runnable, "ainvoke")


def test_generate_cover_letter_text_uses_langchain_runnable(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: CoverLetterRunnableInput) -> str:
            assert task_input.language == "en"
            assert "FastAPI" in task_input.job_description
            assert "Python" in str(task_input.resume_data)
            return "  Tailored cover letter body.  "

    monkeypatch.setattr(
        cover_letter_task_module,
        "build_generate_cover_letter_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_cover_letter_text(
            resume_data={
                "summary": "Python backend engineer",
                "skills": ["Python", "FastAPI"],
            },
            job_description="Senior FastAPI engineer role",
            language="en",
        )
    )

    assert result == "Tailored cover letter body."


def test_generate_cover_letter_text_propagates_task_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: CoverLetterRunnableInput) -> str:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        cover_letter_task_module,
        "build_generate_cover_letter_runnable",
        lambda: FakeRunnable(),
    )

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        asyncio.run(
            generate_cover_letter_text(
                resume_data={"summary": "Python backend engineer"},
                job_description="Senior FastAPI engineer role",
                language="en",
            )
        )


def test_generate_cover_letter_service_delegates_to_ai_task(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_generate_cover_letter_text(**kwargs) -> str:
        assert kwargs["language"] == "ja"
        assert "FastAPI" in kwargs["job_description"]
        return "Delegated cover letter"

    monkeypatch.setattr(
        cover_letter_service_module,
        "generate_cover_letter_text",
        fake_generate_cover_letter_text,
    )

    result = asyncio.run(
        cover_letter_service_module.generate_cover_letter(
            resume_data={"summary": "Python backend engineer"},
            job_description="Senior FastAPI engineer role",
            language="ja",
        )
    )

    assert result == "Delegated cover letter"
