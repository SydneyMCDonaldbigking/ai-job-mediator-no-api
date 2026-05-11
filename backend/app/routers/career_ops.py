"""Career Ops evaluation and tailored PDF endpoints."""

from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from app.career_ops.evaluator import evaluate_job_fit
from app.career_ops.pdf_generator import CareerOpsPDFError, generate_tailored_resume_pdf
from app.career_ops.scanner import scan_portals
from app.career_ops.translator import translate_job_description_to_chinese
from app.schemas import (
    CareerOpsEvaluateRequest,
    CareerOpsEvaluateResponse,
    CareerOpsScanResponse,
    GenerateTailoredPDFRequest,
    TranslateJobDescriptionRequest,
    TranslateJobDescriptionResponse,
)

router = APIRouter(tags=["CareerOps"])


@router.post("/evaluate-job", response_model=CareerOpsEvaluateResponse)
async def evaluate_job_endpoint(
    request: CareerOpsEvaluateRequest,
) -> CareerOpsEvaluateResponse:
    """Return a structured A-F job evaluation for a resume/JD pair."""
    try:
        result = await evaluate_job_fit(
            resume=request.resume,
            job_description=request.job_description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to evaluate the job against the resume.",
        ) from exc

    return CareerOpsEvaluateResponse(
        request_id=str(uuid4()),
        data=result,
    )


@router.post(
    "/translate-job-description",
    response_model=TranslateJobDescriptionResponse,
)
async def translate_job_description_endpoint(
    request: TranslateJobDescriptionRequest,
) -> TranslateJobDescriptionResponse:
    """Translate a JD into Simplified Chinese for frontend display."""
    try:
        translated = await translate_job_description_to_chinese(
            request.job_description,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to translate the job description.",
        ) from exc

    return TranslateJobDescriptionResponse(
        request_id=str(uuid4()),
        translated_job_description=translated,
    )


@router.post("/scan-jobs", response_model=CareerOpsScanResponse)
async def scan_jobs_endpoint() -> CareerOpsScanResponse:
    """Run the portal scanner and return newly discovered offers."""
    try:
        result = await scan_portals()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to scan the configured job portals.",
        ) from exc

    return CareerOpsScanResponse(
        request_id=str(uuid4()),
        data=result,
    )


@router.post("/generate-tailored-pdf")
async def generate_tailored_pdf_endpoint(
    request: GenerateTailoredPDFRequest,
) -> Response:
    """Generate a JD-tailored, ATS-friendly PDF directly from backend HTML."""
    try:
        result = await generate_tailored_resume_pdf(
            resume=request.resume,
            job_description=request.job_description,
            page_size=request.page_size,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except CareerOpsPDFError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate the tailored PDF.",
        ) from exc

    headers = {"Content-Disposition": f'attachment; filename="{result.filename}"'}
    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers=headers,
    )
