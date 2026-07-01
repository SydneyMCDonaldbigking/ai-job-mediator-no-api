from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx

from api_models import (
    CareerOpsEvaluateResponse,
    CareerOpsScanResponse,
    DiscoveredJobRecord,
    ImproveResumeResponse,
    JobUploadResponse,
    MultilingualResumeAssets,
    PortalsConfig,
    ResumeFetchResponse,
    ResumeListResponse,
    ResumeSummary,
    ResumeUploadResponse,
    ScheduledScanConfig,
    ScheduledScanSettingsResponse,
    SeekSearchResponse,
    TranslateJobDescriptionResponse,
)


class ResumeMatcherBackend:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    @staticmethod
    def _extract_filename(content_disposition: str | None, fallback: str) -> str:
        if not content_disposition:
            return fallback
        for part in content_disposition.split(";"):
            part = part.strip()
            if part.lower().startswith("filename="):
                return part.split("=", 1)[1].strip().strip('"') or fallback
        return fallback

    async def upload_resume(
        self,
        file_path: str,
        file_name: str,
        mime_type: str,
        resume_language: str = "en",
    ) -> ResumeUploadResponse:
        with open(file_path, "rb") as handle:
            files = {"file": (file_name, handle, mime_type)}
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/v1/resumes/upload",
                    files=files,
                    data={"resume_language": resume_language},
                )
        response.raise_for_status()
        return ResumeUploadResponse.model_validate(response.json())

    async def get_resume(self, resume_id: str) -> ResumeFetchResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/resumes",
                params={"resume_id": resume_id},
            )
        response.raise_for_status()
        return ResumeFetchResponse.model_validate(response.json())

    async def get_resume_status(self, resume_id: str) -> str:
        payload = await self.get_resume(resume_id)
        return payload.data.raw_resume.processing_status

    async def get_resume_content(self, resume_id: str) -> str:
        payload = await self.get_resume(resume_id)
        return (payload.data.raw_resume.content or "").strip()

    async def list_resumes(self, include_master: bool = True) -> ResumeListResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/resumes/list",
                params={"include_master": str(include_master).lower()},
            )
        response.raise_for_status()
        return ResumeListResponse.model_validate(response.json())

    async def upload_job_description(self, resume_id: str, job_description: str) -> str:
        payload = {
            "job_descriptions": [job_description],
            "resume_id": resume_id,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/jobs/upload",
                json=payload,
            )
        response.raise_for_status()
        result = JobUploadResponse.model_validate(response.json())
        if not result.job_id:
            raise ValueError("后端没有返回有效的 job_id。")
        return result.job_id[0]

    async def preview_resume_improvement(
        self,
        resume_id: str,
        job_id: str,
        prompt_id: str = "keywords",
    ) -> ImproveResumeResponse:
        payload = {
            "resume_id": resume_id,
            "job_id": job_id,
            "prompt_id": prompt_id,
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/resumes/improve/preview",
                json=payload,
            )
        response.raise_for_status()
        return ImproveResumeResponse.model_validate(response.json())

    async def improve_resume(
        self,
        resume_id: str,
        job_id: str,
        prompt_id: str = "keywords",
    ) -> ImproveResumeResponse:
        payload = {
            "resume_id": resume_id,
            "job_id": job_id,
            "prompt_id": prompt_id,
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/resumes/improve",
                json=payload,
            )
        response.raise_for_status()
        return ImproveResumeResponse.model_validate(response.json())

    async def evaluate_job(
        self,
        resume: dict[str, Any] | str,
        job_description: str,
    ) -> CareerOpsEvaluateResponse:
        payload = {
            "resume": resume,
            "job_description": job_description,
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/evaluate-job",
                json=payload,
            )
        response.raise_for_status()
        return CareerOpsEvaluateResponse.model_validate(response.json())

    async def translate_job_description_to_chinese(
        self,
        job_description: str,
    ) -> str:
        payload = {"job_description": job_description}
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/translate-job-description",
                json=payload,
            )
        response.raise_for_status()
        result = TranslateJobDescriptionResponse.model_validate(response.json())
        return result.translated_job_description.strip()

    async def generate_tailored_pdf(
        self,
        resume: dict[str, Any] | str,
        job_description: str,
    ) -> dict[str, Any]:
        payload = {
            "resume": resume,
            "job_description": job_description,
        }
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{self.base_url}/api/generate-tailored-pdf",
                json=payload,
            )
        response.raise_for_status()
        return {
            "filename": self._extract_filename(
                response.headers.get("Content-Disposition"),
                "tailored_resume.pdf",
            ),
            "content": response.content,
        }

    async def scan_jobs(self) -> CareerOpsScanResponse:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{self.base_url}/api/scan-jobs",
            )
        response.raise_for_status()
        return CareerOpsScanResponse.model_validate(response.json())

    async def search_seek_jobs(self, resume_id: str) -> SeekSearchResponse:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/jobs/search/seek",
                json={"resume_id": resume_id},
            )
        response.raise_for_status()
        return SeekSearchResponse.model_validate(response.json())

    async def search_doda_jobs(self, resume_id: str) -> SeekSearchResponse:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/jobs/search/doda",
                json={"resume_id": resume_id},
            )
        response.raise_for_status()
        return SeekSearchResponse.model_validate(response.json())

    async def get_portals_config(self) -> PortalsConfig:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/config/portals",
            )
        response.raise_for_status()
        return PortalsConfig.model_validate(response.json())

    async def update_portals_config(self, config: dict[str, Any]) -> PortalsConfig:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(
                f"{self.base_url}/api/v1/config/portals",
                json=config,
            )
        response.raise_for_status()
        return PortalsConfig.model_validate(response.json())

    async def get_scheduled_scan_settings(self) -> ScheduledScanSettingsResponse:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}/api/v1/scheduled-scan/settings",
            )
        response.raise_for_status()
        return ScheduledScanSettingsResponse.model_validate(response.json())

    async def update_scheduled_scan_settings(
        self,
        config: dict[str, Any],
    ) -> ScheduledScanSettingsResponse:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.put(
                f"{self.base_url}/api/v1/scheduled-scan/settings",
                json=config,
            )
        response.raise_for_status()
        return ScheduledScanSettingsResponse.model_validate(response.json())

    async def mark_discovered_job_status(
        self,
        job_key: str,
        status: str,
    ) -> DiscoveredJobRecord:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/scheduled-scan/jobs/status",
                json={"job_key": job_key, "status": status},
            )
        response.raise_for_status()
        return DiscoveredJobRecord.model_validate(response.json())


class InMemoryTestBackend:
    """Tiny in-process backend used by browser smoke tests."""

    SIMPLE_PDF_BYTES = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

    def __init__(self) -> None:
        self.resume_id = "test-master-resume"
        self.resume_content = "Test resume\nSkills: Python, FastAPI, APIs"
        self.last_uploaded_name = ""
        self.resume_filenames = {
            self.resume_id: "test-master-resume.pdf",
            "test-ja-resume": "test-ja-resume.pdf",
        }
        self.job_counter = 0
        self.job_descriptions: dict[str, str] = {}
        self.multilingual_assets = MultilingualResumeAssets(
            resume_en_id=self.resume_id,
            resume_ja_id="test-ja-resume",
            updated_at="2026-04-17T00:00:00+00:00",
        )
        sample_recent_jobs = [
            {
                "job_key": "seek:https://www.seek.com.au/job/123",
                "source": "seek",
                "resume_language": "en",
                "title": "Senior Backend Engineer",
                "company": "Example Co",
                "location": "Sydney NSW",
                "job_url": "https://www.seek.com.au/job/123",
                "summary": "Build APIs",
                "match_score": 0.91,
                "discovered_at": "2026-04-17T00:05:00+00:00",
                "first_seen_at": "2026-04-17T00:05:00+00:00",
                "last_seen_at": "2026-04-17T00:05:00+00:00",
                "is_new": True,
                "status": "new",
            }
        ]
        sample_high_score_jobs = sample_recent_jobs + [
            {
                "job_key": "seek:https://www.seek.com.au/job/456",
                "source": "seek",
                "resume_language": "en",
                "title": "Staff Platform Engineer",
                "company": "Example Co",
                "location": "Melbourne VIC",
                "job_url": "https://www.seek.com.au/job/456",
                "summary": "Build platforms",
                "match_score": 0.96,
                "discovered_at": "2026-04-17T00:10:00+00:00",
                "first_seen_at": "2026-04-17T00:10:00+00:00",
                "last_seen_at": "2026-04-17T00:10:00+00:00",
                "is_new": True,
                "status": "new",
            }
        ]
        self.scheduled_scan_settings = ScheduledScanSettingsResponse.model_validate(
            {
                "config": {
                    "enabled": False,
                    "run_time_local": "09:00",
                    "timezone": "Australia/Sydney",
                    "seek_enabled": True,
                    "doda_enabled": False,
                    "boss_enabled": False,
                    "feishu_enabled": False,
                    "feishu_webhook_url": None,
                    "high_score_threshold": 0.75,
                    "last_run_at": None,
                    "last_run_date_local": None,
                    "last_run_status": None,
                    "last_error": None,
                    "last_result_counts": {
                        "seek": {"raw_jobs_found": 7, "new_jobs": 2}
                    },
                },
                "assets": self.multilingual_assets.model_dump(),
                "recent_new_jobs": sample_recent_jobs,
                "high_score_unapplied_jobs": sample_high_score_jobs,
            }
        )
        self.portals_config = PortalsConfig.model_validate(
            {
                "title_filter": {
                    "positive": ["engineer", "backend"],
                    "negative": ["intern"],
                    "seniority_boost": ["senior", "staff"],
                },
                "search_queries": [
                    {
                        "name": "backend",
                        "query": "python backend engineer",
                        "enabled": True,
                    }
                ],
                "tracked_companies": [
                    {
                        "name": "Anthropic",
                        "careers_url": "https://jobs.example.com/anthropic",
                        "enabled": True,
                        "api": "greenhouse",
                    }
                ],
            }
        )

    def _build_resume_content(self, file_name: str, mime_type: str) -> str:
        extension = Path(file_name).suffix.lower()
        document_label = extension.lstrip(".") or mime_type or "resume"
        return (
            f"Master resume imported from {file_name}.\n"
            f"Document type: {document_label}.\n"
            "Core skills: Python, FastAPI, SQL, distributed systems."
        )

    def _build_improvements(self, job_description: str) -> list[dict[str, Any]]:
        suggestions = [
            {
                "suggestion": "Highlight measurable backend delivery wins that match the JD.",
                "lineNumber": 3,
            },
            {
                "suggestion": "Surface Python and FastAPI keywords earlier in the summary.",
                "lineNumber": 6,
            },
        ]
        if "distributed" in job_description.casefold():
            suggestions.append(
                {
                    "suggestion": "Add one bullet about distributed systems reliability work.",
                    "lineNumber": 9,
                }
            )
        return suggestions

    def _build_improve_payload(
        self,
        *,
        job_id: str,
        job_description: str,
        include_resume_id: bool,
    ) -> ImproveResumeResponse:
        suggestions = self._build_improvements(job_description)
        return ImproveResumeResponse.model_validate(
            {
                "request_id": f"test-{job_id}",
                "data": {
                    "resume_id": "tailored-test-resume" if include_resume_id else None,
                    "job_id": job_id,
                    "improvements": suggestions,
                    "markdownImproved": (
                        (
                            "# Tailored Resume\n\n"
                            f"Optimized for: {job_description[:120]}\n\n"
                            "- Python\n- FastAPI\n- Delivery impact\n"
                        )
                        if include_resume_id
                        else None
                    ),
                    "cover_letter": (
                        "Short targeted cover letter." if include_resume_id else None
                    ),
                    "outreach_message": (
                        "Hi, I would love to discuss the role."
                        if include_resume_id
                        else None
                    ),
                    "diff_summary": {
                        "total_changes": len(suggestions) + 1,
                        "skills_added": 2,
                        "skills_removed": 0,
                        "descriptions_modified": 2,
                        "certifications_added": 0,
                        "high_risk_changes": 0,
                    },
                    "refinement_stats": {
                        "initial_match_percentage": 62.0,
                        "final_match_percentage": 84.0,
                    },
                    "warnings": [],
                },
            }
        )

    async def upload_resume(
        self,
        file_path: str,
        file_name: str,
        mime_type: str,
        resume_language: str = "en",
    ) -> ResumeUploadResponse:
        del file_path
        self.last_uploaded_name = file_name
        language_to_resume_id = {
            "en": self.resume_id,
            "ja": "test-ja-resume",
            "zh": "test-zh-resume",
        }
        resume_id = language_to_resume_id.get(resume_language, self.resume_id)
        self.resume_filenames[resume_id] = file_name
        if resume_language == "en":
            self.resume_content = self._build_resume_content(file_name, mime_type)
        self.multilingual_assets = self.multilingual_assets.model_copy(
            update={
                f"resume_{resume_language}_id": resume_id,
                "updated_at": "2026-04-17T00:00:00+00:00",
            }
        )
        self.scheduled_scan_settings = self.scheduled_scan_settings.model_copy(
            update={"assets": self.multilingual_assets}
        )
        return ResumeUploadResponse(
            message="stored",
            request_id="test-upload",
            resume_id=resume_id,
            processing_status="ready",
            is_master=resume_language == "en",
        )

    async def get_resume(self, resume_id: str) -> ResumeFetchResponse:
        del resume_id
        return ResumeFetchResponse.model_validate(
            {
                "data": {
                    "raw_resume": {
                        "content": self.resume_content,
                        "processing_status": "ready",
                    },
                    "cover_letter": None,
                    "outreach_message": None,
                }
            }
        )

    async def get_resume_status(self, resume_id: str) -> str:
        del resume_id
        return "ready"

    async def get_resume_content(self, resume_id: str) -> str:
        del resume_id
        return self.resume_content

    async def upload_job_description(self, resume_id: str, job_description: str) -> str:
        del resume_id
        self.job_counter += 1
        job_id = f"job-{self.job_counter}"
        self.job_descriptions[job_id] = job_description
        return job_id

    async def preview_resume_improvement(
        self,
        resume_id: str,
        job_id: str,
        prompt_id: str = "keywords",
    ) -> ImproveResumeResponse:
        del resume_id, prompt_id
        return self._build_improve_payload(
            job_id=job_id,
            job_description=self.job_descriptions.get(job_id, "preview analysis"),
            include_resume_id=False,
        )

    async def improve_resume(
        self,
        resume_id: str,
        job_id: str,
        prompt_id: str = "keywords",
    ) -> ImproveResumeResponse:
        del resume_id, prompt_id
        return self._build_improve_payload(
            job_id=job_id,
            job_description=self.job_descriptions.get(
                job_id,
                "Responsibilities: build APIs. Requirements: Python and FastAPI.",
            ),
            include_resume_id=True,
        )

    async def evaluate_job(
        self,
        resume: dict[str, Any] | str,
        job_description: str,
    ) -> CareerOpsEvaluateResponse:
        del resume
        return CareerOpsEvaluateResponse.model_validate(
            {
                "request_id": "test-evaluate",
                "data": {
                    "overall_score": 4.3,
                    "overall_label": "Strong fit",
                    "executive_summary": "Strong alignment with the target backend scope.",
                    "archetype": "Builder",
                    "af_scores": {
                        "A": 4.5,
                        "B": 4.2,
                        "C": 4.1,
                        "D": 3.8,
                        "E": 4.4,
                        "F": 4.6,
                    },
                    "dimensions": [],
                    "tailoring_priorities": [
                        "Bring backend delivery metrics closer to the top of the resume."
                    ],
                    "interview_focus": [
                        "Prepare one story about shipping APIs under ambiguity."
                    ],
                    "keyword_targets": ["Python", "FastAPI", "APIs"],
                    "market_data": {
                        "role_query": "Backend Engineer",
                        "company_name": "Test Company",
                        "salary_mentions": ["$160,000 base"],
                        "demand_summary": "Demand remains healthy for backend hires.",
                        "compensation_summary": "Compensation looks competitive for the role.",
                        "sources": [
                            {
                                "title": "Mock market source",
                                "url": "https://example.com/market",
                                "snippet": job_description[:80],
                            }
                        ],
                    },
                },
            }
        )

    async def translate_job_description_to_chinese(
        self,
        job_description: str,
    ) -> str:
        if "岗位" in job_description or "职责" in job_description:
            return job_description
        return (
            "岗位职责：根据搜索结果摘要评估岗位匹配度。\n"
            "任职要求：保留原始技术关键词、公司名称和链接。\n\n"
            f"原文参考：{job_description}"
        )

    async def generate_tailored_pdf(
        self,
        resume: dict[str, Any] | str,
        job_description: str,
    ) -> dict[str, Any]:
        del resume, job_description
        return {
            "filename": "tailored_resume.pdf",
            "content": self.SIMPLE_PDF_BYTES,
        }

    async def scan_jobs(self) -> CareerOpsScanResponse:
        return CareerOpsScanResponse.model_validate(
            {
                "request_id": "test-scan",
                "data": {
                    "scanned_companies": 1,
                    "total_jobs_found": 1,
                    "filtered_out": 0,
                    "duplicates": 0,
                    "new_offers": [
                        {
                            "title": "Senior Backend Engineer",
                            "url": "https://example.com/jobs/backend",
                            "company": "Anthropic",
                            "location": "Remote",
                            "source": "greenhouse",
                        }
                    ],
                    "errors": [],
                },
            }
        )

    async def search_seek_jobs(self, resume_id: str) -> SeekSearchResponse:
        del resume_id
        return SeekSearchResponse.model_validate(
            {
                "plan": {
                    "resume_id": self.resume_id,
                    "source": "seek",
                    "candidate_profile_summary": "Python backend engineer with API and platform experience.",
                    "keywords": ["python backend engineer", "platform engineer"],
                    "location": "Sydney NSW",
                },
                "jobs": [
                    {
                        "job_id": "seek:https://www.seek.com.au/job/123",
                        "source": "seek",
                        "search_keyword": "python backend engineer",
                        "title": "Senior Backend Engineer",
                        "company": "Example Co",
                        "location": "Sydney NSW",
                        "salary": "$180k-$200k",
                        "work_type": "Full time",
                        "listed_at": "2d ago",
                        "job_url": "https://www.seek.com.au/job/123",
                        "summary": "Build APIs and platform services.",
                        "match_score": 0.91,
                    }
                ],
                "stats": {
                    "keywords_generated": 2,
                    "queries_attempted": 2,
                    "queries_succeeded": 2,
                    "raw_jobs_found": 3,
                    "jobs_after_dedupe": 1,
                },
                "errors": [],
            }
        )

    async def search_doda_jobs(self, resume_id: str) -> SeekSearchResponse:
        del resume_id
        return SeekSearchResponse.model_validate(
            {
                "plan": {
                    "resume_id": self.multilingual_assets.resume_ja_id
                    or "test-ja-resume",
                    "source": "doda",
                    "candidate_profile_summary": "Python と FastAPI を使ったバックエンド開発経験。",
                    "keywords": ["バックエンドエンジニア", "Python エンジニア"],
                    "location": "東京",
                },
                "jobs": [
                    {
                        "job_id": "doda:https://doda.jp/job/123",
                        "source": "doda",
                        "language": "ja",
                        "search_keyword": "バックエンドエンジニア",
                        "title": "バックエンドエンジニア",
                        "company": "OpenAI Japan",
                        "location": "東京",
                        "salary": "年収700万円-1000万円",
                        "work_type": None,
                        "listed_at": None,
                        "job_url": "https://doda.jp/job/123",
                        "summary": "Python / FastAPI / API 開発",
                        "match_score": 0.89,
                        "raw_location_text": "東京",
                        "raw_salary_text": "年収700万円-1000万円",
                    }
                ],
                "stats": {
                    "keywords_generated": 2,
                    "queries_attempted": 2,
                    "queries_succeeded": 2,
                    "raw_jobs_found": 2,
                    "jobs_after_dedupe": 1,
                },
                "errors": [],
            }
        )

    async def get_portals_config(self) -> PortalsConfig:
        return self.portals_config.model_copy(deep=True)

    async def update_portals_config(self, config: dict[str, Any]) -> PortalsConfig:
        self.portals_config = PortalsConfig.model_validate(config)
        return self.portals_config.model_copy(deep=True)

    async def list_resumes(self, include_master: bool = True) -> ResumeListResponse:
        del include_master
        resume_ids = [
            self.multilingual_assets.resume_en_id,
            self.multilingual_assets.resume_ja_id,
            self.multilingual_assets.resume_zh_id,
        ]
        summaries = []
        for resume_id in resume_ids:
            if not resume_id:
                continue
            summaries.append(
                ResumeSummary(
                    resume_id=resume_id,
                    filename=self.resume_filenames.get(resume_id),
                    is_master=resume_id == self.resume_id,
                    processing_status="ready",
                    created_at=self.multilingual_assets.updated_at or "",
                    updated_at=self.multilingual_assets.updated_at or "",
                )
            )
        return ResumeListResponse(request_id="test-resume-list", data=summaries)

    async def get_scheduled_scan_settings(self) -> ScheduledScanSettingsResponse:
        return self.scheduled_scan_settings.model_copy(deep=True)

    async def update_scheduled_scan_settings(
        self,
        config: dict[str, Any],
    ) -> ScheduledScanSettingsResponse:
        validated = ScheduledScanConfig.model_validate(config)
        self.scheduled_scan_settings = self.scheduled_scan_settings.model_copy(
            update={"config": validated, "assets": self.multilingual_assets}
        )
        return self.scheduled_scan_settings.model_copy(deep=True)

    async def mark_discovered_job_status(
        self,
        job_key: str,
        status: str,
    ) -> DiscoveredJobRecord:
        updated_job: DiscoveredJobRecord | None = None
        recent_jobs: list[DiscoveredJobRecord] = []
        for job in self.scheduled_scan_settings.recent_new_jobs:
            candidate = job
            if job.job_key == job_key:
                candidate = job.model_copy(update={"status": status})
                updated_job = candidate
            recent_jobs.append(candidate)
        high_score_jobs: list[DiscoveredJobRecord] = []
        for job in self.scheduled_scan_settings.high_score_unapplied_jobs:
            if job.job_key == job_key and status == "applied":
                updated_job = updated_job or job.model_copy(update={"status": status})
                continue
            candidate = job
            if job.job_key == job_key:
                candidate = job.model_copy(update={"status": status})
                updated_job = candidate
            high_score_jobs.append(candidate)
        if updated_job:
            self.scheduled_scan_settings = self.scheduled_scan_settings.model_copy(
                update={
                    "recent_new_jobs": recent_jobs,
                    "high_score_unapplied_jobs": high_score_jobs,
                }
            )
            return updated_job
        raise ValueError(f"Job not found: {job_key}")
