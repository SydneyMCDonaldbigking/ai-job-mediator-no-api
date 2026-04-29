import asyncio
import importlib
import json

import pytest

from app.ai.parsers.parse_resume import parse_resume_json
from app.ai.tasks.parse_resume import (
    ParseResumeRunnableInput,
    build_parse_resume_runnable,
    generate_parsed_resume,
)
from app.schemas.models import ResumeData
from app.services import parser as parser_service_module

parse_resume_task_module = importlib.import_module("app.ai.tasks.parse_resume")


def test_build_parse_resume_runnable_returns_ainvokable_pipeline():
    runnable = build_parse_resume_runnable()
    assert hasattr(runnable, "ainvoke")


def test_parse_resume_json_returns_structured_resume_data():
    payload = json.dumps(
        {
            "personalInfo": {
                "name": "Jane Doe",
                "title": "Backend Engineer",
                "email": "jane@example.com",
            },
            "summary": "Experienced backend engineer",
            "workExperience": [
                {
                    "id": 1,
                    "title": "Software Engineer",
                    "company": "Acme",
                    "years": "2020 - Present",
                    "description": ["Built APIs"],
                }
            ],
            "additional": {"technicalSkills": ["Python", "FastAPI"]},
        }
    )

    result = parse_resume_json(payload)

    assert result.personalInfo.name == "Jane Doe"
    assert result.workExperience[0].company == "Acme"
    assert result.additional.technicalSkills == ["Python", "FastAPI"]


def test_parse_resume_json_normalizes_nested_whitespace():
    payload = json.dumps(
        {
            "personalInfo": {"name": "  Jane Doe  ", "title": " Backend Engineer "},
            "summary": "  Experienced backend engineer  ",
            "workExperience": [
                {
                    "id": 1,
                    "title": " Senior Engineer ",
                    "company": " Acme ",
                    "years": " 2020 - Present ",
                    "description": ["  Built APIs  ", "\n- Improved latency\n"],
                }
            ],
            "additional": {"technicalSkills": [" Python ", " FastAPI "]},
        }
    )

    result = parse_resume_json(payload)

    assert result.personalInfo.name == "Jane Doe"
    assert result.personalInfo.title == "Backend Engineer"
    assert result.summary == "Experienced backend engineer"
    assert result.workExperience[0].title == "Senior Engineer"
    assert result.workExperience[0].company == "Acme"
    assert result.workExperience[0].description == ["Built APIs", "Improved latency"]
    assert result.additional.technicalSkills == ["Python", "FastAPI"]


def test_generate_parsed_resume_uses_langchain_runnable(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: ParseResumeRunnableInput) -> dict[str, object]:
            assert "Backend Engineer" in task_input.resume_text
            return {
                "personalInfo": {"name": " Jane Doe "},
                "summary": " Experienced backend engineer ",
                "workExperience": [
                    {
                        "id": 1,
                        "title": " Software Engineer ",
                        "company": " Acme ",
                        "years": " 2020 - Present ",
                        "description": [" Built APIs "],
                    }
                ],
            }

    monkeypatch.setattr(
        parse_resume_task_module,
        "build_parse_resume_runnable",
        lambda: FakeRunnable(),
    )

    result = asyncio.run(
        generate_parsed_resume(resume_text="Jane Doe\nBackend Engineer\nBuilt APIs")
    )

    assert result.personalInfo.name == "Jane Doe"
    assert result.summary == "Experienced backend engineer"
    assert result.workExperience[0].company == "Acme"


def test_generate_parsed_resume_propagates_task_errors(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeRunnable:
        async def ainvoke(self, task_input: ParseResumeRunnableInput) -> dict[str, object]:
            raise RuntimeError("LLM unavailable")

    monkeypatch.setattr(
        parse_resume_task_module,
        "build_parse_resume_runnable",
        lambda: FakeRunnable(),
    )

    with pytest.raises(RuntimeError, match="LLM unavailable"):
        asyncio.run(generate_parsed_resume(resume_text="Jane Doe\nBackend Engineer"))


def test_parse_resume_to_json_service_delegates_and_restores_dates(
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_generate_parsed_resume(**kwargs) -> ResumeData:
        assert "Jane Doe" in kwargs["resume_text"]
        return ResumeData.model_validate(
            {
                "personalInfo": {"name": "Jane Doe"},
                "summary": "Backend engineer",
                "workExperience": [
                    {
                        "id": 1,
                        "title": "Software Engineer",
                        "company": "Acme",
                        "years": "2020 - 2021",
                        "description": ["Built APIs"],
                    }
                ],
            }
        )

    monkeypatch.setattr(
        parser_service_module,
        "generate_parsed_resume",
        fake_generate_parsed_resume,
    )

    result = asyncio.run(
        parser_service_module.parse_resume_to_json(
            "Jane Doe\nSoftware Engineer\nAcme\nJun 2020 - Aug 2021"
        )
    )

    assert result["workExperience"][0]["years"] == "Jun 2020 - Aug 2021"
