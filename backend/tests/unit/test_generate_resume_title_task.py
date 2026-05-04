import asyncio
import importlib

import pytest

from app.ai.tasks.generate_resume_title import (
    ResumeTitleRunnableInput,
    build_generate_resume_title_runnable,
    generate_resume_title_text,
    normalize_generated_resume_title,
)
from app.services import cover_letter as cover_letter_service_module

resume_title_task_module = importlib.import_module("app.ai.tasks.generate_resume_title")


def test_build_generate_resume_title_runnable_returns_ainvokable_pipeline():
    runnable = build_generate_resume_title_runnable()
    assert hasattr(runnable, "ainvoke")


def test_generate_resume_title_text_normalizes_quotes_whitespace_and_length(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: ResumeTitleRunnableInput) -> str:
            assert task_input.language == "en"
            assert "Stripe" in task_input.job_description
            return '   "Senior Frontend Engineer @ Stripe' + ("X" * 90) + '"   '

    monkeypatch.setattr(
        resume_title_task_module,
        "build_generate_resume_title_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_resume_title_text(
            job_description="Stripe is hiring a Senior Frontend Engineer.",
            language="en",
        )
    )

    assert result == normalize_generated_resume_title(
        '   "Senior Frontend Engineer @ Stripe' + ("X" * 90) + '"   '
    )
    assert result.startswith('"Senior Frontend Engineer')
    assert result.endswith('"')


def test_normalize_generated_resume_title_strips_surrounding_whitespace():
    assert (
        normalize_generated_resume_title(
            "  'Backend Engineer @ Canva" + ("Y" * 100) + "'  "
        )
        == "'Backend Engineer @ Canva" + ("Y" * 100) + "'"
    )


def test_generate_resume_title_text_propagates_task_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: ResumeTitleRunnableInput) -> str:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        resume_title_task_module,
        "build_generate_resume_title_runnable",
        lambda: FakeRunnable(),
    )

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        asyncio.run(
            generate_resume_title_text(
                job_description="Stripe is hiring a Senior Frontend Engineer.",
                language="en",
            )
        )


def test_generate_resume_title_service_delegates_and_preserves_cleanup(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_generate_resume_title_text(**kwargs) -> str:
        assert kwargs["language"] == "ja"
        assert "Stripe" in kwargs["job_description"]
        return '  "Senior Frontend Engineer @ Stripe' + ("Z" * 90) + '"  '

    monkeypatch.setattr(
        cover_letter_service_module,
        "generate_resume_title_text",
        fake_generate_resume_title_text,
    )

    result = asyncio.run(
        cover_letter_service_module.generate_resume_title(
            job_description="Stripe is hiring a Senior Frontend Engineer.",
            language="ja",
        )
    )

    assert result == ("Senior Frontend Engineer @ Stripe" + ("Z" * 47))[:80]
    assert len(result) == 80
    assert '"' not in result
