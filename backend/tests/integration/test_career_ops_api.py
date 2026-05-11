"""Integration tests for Career Ops API endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.models import CareerOpsEvaluationData, CareerOpsScoreDimension, TailoredPDFResult


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@patch("app.routers.career_ops.evaluate_job_fit", new_callable=AsyncMock)
async def test_evaluate_job_returns_structured_scores(
    mock_evaluate,
    client,
    sample_resume,
    sample_job_description,
):
    mock_evaluate.return_value = CareerOpsEvaluationData(
        overall_score=4.3,
        overall_label="strong-match",
        executive_summary="Strong backend fit with one infrastructure gap.",
        archetype="agentic-platform",
        af_scores={"A": 4.5, "B": 4.0, "C": 4.0, "D": 3.5, "E": 5.0, "F": 4.5},
        dimensions=[
            CareerOpsScoreDimension(
                key="archetype_fit",
                category="A",
                label="Archetype Fit",
                score=4.5,
                rationale="Backend platform work matches the JD well.",
                evidence=["Built scalable APIs with FastAPI."],
                risks=["Limited Kubernetes depth."],
            )
        ],
        tailoring_priorities=["Move FastAPI and AWS higher in summary."],
        interview_focus=["Prepare one architecture migration story."],
        keyword_targets=["Python", "FastAPI", "AWS"],
    )

    async with client:
        response = await client.post(
            "/api/evaluate-job",
            json={
                "resume": sample_resume,
                "job_description": sample_job_description,
            },
        )

    assert response.status_code == 200
    payload = response.json()["data"]
    assert payload["overall_score"] == 4.3
    assert payload["af_scores"]["A"] == 4.5
    assert payload["dimensions"][0]["key"] == "archetype_fit"


@patch("app.routers.career_ops.translate_job_description_to_chinese", new_callable=AsyncMock)
async def test_translate_job_description_to_chinese_returns_translated_text(
    mock_translate,
    client,
):
    mock_translate.return_value = "岗位职责：构建 API。任职要求：Python。"

    async with client:
        response = await client.post(
            "/api/translate-job-description",
            json={
                "job_description": "Responsibilities: Build APIs. Requirements: Python.",
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["translated_job_description"] == "岗位职责：构建 API。任职要求：Python。"
    mock_translate.assert_awaited_once_with(
        "Responsibilities: Build APIs. Requirements: Python."
    )


@patch("app.routers.career_ops.generate_tailored_resume_pdf", new_callable=AsyncMock)
async def test_generate_tailored_pdf_returns_pdf_bytes(
    mock_generate_pdf,
    client,
    sample_resume,
    sample_job_description,
):
    mock_generate_pdf.return_value = TailoredPDFResult(
        filename="jane-doe-tailored.pdf",
        pdf_bytes=b"%PDF-1.4\nmock pdf\n",
        tailored_resume=sample_resume,
        keyword_targets=["Python", "FastAPI"],
    )

    async with client:
        response = await client.post(
            "/api/generate-tailored-pdf",
            json={
                "resume": sample_resume,
                "job_description": sample_job_description,
            },
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "attachment; filename=\"jane-doe-tailored.pdf\"" == response.headers[
        "content-disposition"
    ]
    assert response.content.startswith(b"%PDF-1.4")
