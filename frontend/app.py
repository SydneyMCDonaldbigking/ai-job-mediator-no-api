from __future__ import annotations
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
load_dotenv()
os.environ.setdefault(
    "CHAINLIT_AUTH_SECRET",
    os.getenv("CHAINLIT_AUTH_SECRET")
    or "local-dev-secret-change-me-2026-very-long",
)
import chainlit as cl
import httpx
import yaml
from chainlit.context import context
from chainlit.types import ThreadDict
from pydantic import BaseModel, Field
from backend_chat_store import BackendTinyDBDataLayer
from local_chat_store import LocalJsonDataLayer
APP_DIR = Path(__file__).resolve().parent
def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}
TEST_MODE_ENABLED = env_flag("CHAINLIT_TEST_MODE")
DATA_DIR = Path(os.getenv("CHAINLIT_APP_DATA_DIR") or (APP_DIR / "data"))
PUBLIC_DIR = Path(os.getenv("CHAINLIT_APP_PUBLIC_DIR") or (APP_DIR / "public"))
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5-72b")
APP_USERNAME = os.getenv("CHAINLIT_APP_USERNAME", "local-user")
APP_PASSWORD = os.getenv("CHAINLIT_APP_PASSWORD", "job-mediator-123")
APP_DISPLAY_NAME = os.getenv("CHAINLIT_APP_DISPLAY_NAME", "Local User")
AUTO_LOGIN_ENABLED = env_flag("CHAINLIT_AUTO_LOGIN", default=True)
SYSTEM_PROMPT = (
    "你是一位经验丰富、热情专业的 AI 求职中介。"
    "语气亲切、直接、实用，优先帮用户推进下一步。"
)
WELCOME_MESSAGE = (
    "你好！我是你的 AI 求职中介助手。请先上传你的主简历（PDF 或 Word），"
    "上传完成后我就可以帮你分析职位、优化简历、生成自我介绍等。"
)
UPLOAD_SUCCESS_MESSAGE = (
    "简历上传成功！现在告诉我你的需求，例如："
    "帮我分析适合哪些职位、给我一个 JD 帮我优化等。"
)
SESSION_RESUME_ID = "resume_id"
SESSION_RESUME_STATUS = "resume_status"
SESSION_LAST_UPLOAD_NAME = "last_upload_name"
SESSION_LAST_TAILORED_RESUME_ID = "tailored_resume_id"
SESSION_LAST_JOB_DESCRIPTION = "last_job_description"
SESSION_THREAD_NAMED = "thread_named"
SESSION_PENDING_ACTION = "pending_action"
SESSION_SCHEDULED_SCAN_EDIT_FIELD = "scheduled_scan_edit_field"
SUPPORTED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}
SUPPORTED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
FILE_ACCEPT_CONFIG = {
    "application/pdf": [".pdf"],
    "application/msword": [".doc"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
}
ANALYSIS_KEYWORDS = (
    "分析",
    "匹配",
    "match",
    "analysis",
    "analyze",
    "recommend",
    "推荐职位",
)
EVALUATE_KEYWORDS = (
    "a-f",
    "af",
    "evaluate",
    "evaluation",
    "职位评估",
    "岗位评估",
    "career ops",
    "oferta",
)
OPTIMIZE_KEYWORDS = (
    "优化简历",
    "优化",
    "tailor",
    "tailoring",
    "improve",
    "optimize",
    "job description",
    "jd",
)
SCAN_KEYWORDS = (
    "扫描职位",
    "扫描岗位",
    "scan jobs",
    "scan portals",
    "扫职位",
)
PORTALS_VIEW_KEYWORDS = (
    "portals",
    "portal 配置",
    "查看 portals",
    "查看 portal",
    "职位源配置",
)
PORTALS_EDIT_KEYWORDS = (
    "更新 portals",
    "编辑 portals",
    "修改 portals",
    "更新 portal",
    "编辑 portal",
)
SCHEDULED_SCAN_VIEW_KEYWORDS = (
    "自动扫描",
    "定时扫描",
    "scheduled scan",
    "scan settings",
)
SCHEDULED_SCAN_EDIT_KEYWORDS = (
    "更新自动扫描",
    "修改自动扫描",
    "编辑自动扫描",
    "update scheduled scan",
)
JD_MARKERS = (
    "职责",
    "要求",
    "任职资格",
    "岗位描述",
    "qualification",
    "qualifications",
    "responsibilities",
    "requirements",
    "about the role",
    "what you'll do",
)
ACTION_EVALUATE_JOB = "career_ops_evaluate_job"
ACTION_REUPLOAD_MASTER_RESUME = "career_ops_reupload_master_resume"
ACTION_DOWNLOAD_TAILORED_PDF = "career_ops_download_tailored_pdf"
ACTION_SCAN_JOBS = "career_ops_scan_jobs"
ACTION_SEARCH_SEEK = "career_ops_search_seek"
ACTION_SEARCH_DODA = "career_ops_search_doda"
ACTION_VIEW_PORTALS = "career_ops_view_portals"
ACTION_EDIT_PORTALS = "career_ops_edit_portals"
ACTION_UPLOAD_EN_RESUME = "career_ops_upload_en_resume"
ACTION_UPLOAD_JA_RESUME = "career_ops_upload_ja_resume"
ACTION_UPLOAD_ZH_RESUME = "career_ops_upload_zh_resume"
ACTION_VIEW_SCHEDULED_SCAN = "career_ops_view_scheduled_scan"
ACTION_EDIT_SCHEDULED_SCAN = "career_ops_edit_scheduled_scan"
ACTION_MARK_JOB_APPLIED = "career_ops_mark_job_applied"
ACTION_TOGGLE_SCHEDULED_SCAN_FIELD = "career_ops_toggle_scheduled_scan_field"
ACTION_PROMPT_SCHEDULED_SCAN_FIELD = "career_ops_prompt_scheduled_scan_field"
ACTION_DELETE_CURRENT_THREAD = "career_ops_delete_current_thread"
from chainlit.chat_settings import ChatSettings
from chainlit.input_widget import Slider, Switch, TextInput
PENDING_EVALUATE_JOB = "evaluate_job"
PENDING_DOWNLOAD_TAILORED_PDF = "download_tailored_pdf"
PENDING_UPDATE_PORTALS = "update_portals"
PENDING_UPDATE_SCHEDULED_SCAN = "update_scheduled_scan"
FRONTEND_DIR = Path(__file__).resolve().parent
if str(FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(FRONTEND_DIR))
class ResumeUploadResponse(BaseModel):
    message: str
    request_id: str
    resume_id: str
    processing_status: str = "pending"
    is_master: bool = False
class RawResume(BaseModel):
    content: str | None = None
    processing_status: str = "pending"
class ResumeFetchData(BaseModel):
    raw_resume: RawResume
    cover_letter: str | None = None
    outreach_message: str | None = None
SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE = "scheduled_scan_settings_form_active"
class ResumeFetchResponse(BaseModel):
    data: ResumeFetchData
def normalize_scheduled_scan_settings_input(settings: dict[str, Any]) -> dict[str, Any]:
    return {
        "enabled": bool(settings.get("scheduled_scan_enabled")),
        "run_time_local": parse_scheduled_scan_field_input(
            "run_time_local",
            str(settings.get("scheduled_scan_run_time_local", "")),
        ),
        "timezone": str(settings.get("scheduled_scan_timezone", "")).strip(),
        "high_score_threshold": parse_scheduled_scan_field_input(
            "high_score_threshold",
            str(settings.get("scheduled_scan_high_score_threshold", "")),
        ),
        "seek_enabled": bool(settings.get("scheduled_scan_seek_enabled")),
        "doda_enabled": bool(settings.get("scheduled_scan_doda_enabled")),
        "boss_enabled": bool(settings.get("scheduled_scan_boss_enabled")),
        "feishu_enabled": bool(settings.get("scheduled_scan_feishu_enabled")),
        "feishu_webhook_url": parse_scheduled_scan_field_input(
            "feishu_webhook_url",
            str(settings.get("scheduled_scan_feishu_webhook_url", "")),
        ),
    }


def build_scheduled_scan_chat_settings(
    config: ScheduledScanConfig,
    assets: MultilingualResumeAssets,
) -> ChatSettings:
    return ChatSettings(
        inputs=[
            Switch(
                id="scheduled_scan_enabled",
                label="Enable auto scan",
                initial=config.enabled,
                tooltip="Master switch for the daily scan.",
            ),
            TextInput(
                id="scheduled_scan_run_time_local",
                label="Run time",
                initial=config.run_time_local,
                placeholder="21:30",
                tooltip="Use HH:MM format.",
            ),
            TextInput(
                id="scheduled_scan_timezone",
                label="Timezone",
                initial=config.timezone,
                placeholder="Australia/Sydney",
                tooltip="Use an IANA timezone name.",
            ),
            Slider(
                id="scheduled_scan_high_score_threshold",
                label="High score threshold",
                initial=config.high_score_threshold,
                min=0,
                max=1,
                step=0.05,
                tooltip="Only jobs at or above this score count as high-score unapplied.",
            ),
            Switch(
                id="scheduled_scan_seek_enabled",
                label="Enable SEEK",
                initial=config.seek_enabled,
                disabled=not bool(assets.resume_en_id),
                tooltip="Requires an English resume.",
            ),
            Switch(
                id="scheduled_scan_doda_enabled",
                label="Enable doda",
                initial=config.doda_enabled,
                disabled=not bool(assets.resume_ja_id),
                tooltip="Requires a Japanese resume.",
            ),
            Switch(
                id="scheduled_scan_boss_enabled",
                label="Enable BOSS",
                initial=config.boss_enabled,
                disabled=not bool(assets.resume_zh_id),
                tooltip="Requires a Chinese resume.",
            ),
            Switch(
                id="scheduled_scan_feishu_enabled",
                label="Enable Feishu notifications",
                initial=config.feishu_enabled,
                tooltip="Notify only for high-score unapplied jobs.",
            ),
            TextInput(
                id="scheduled_scan_feishu_webhook_url",
                label="Feishu webhook",
                initial=config.feishu_webhook_url or "",
                placeholder="https://open.feishu.cn/...",
                tooltip="Leave blank or set to none to clear.",
            ),
        ]
    )
class JobUploadResponse(BaseModel):
    message: str
    job_id: list[str]
class ImprovementSuggestion(BaseModel):
    suggestion: str
    lineNumber: int | None = None
class ResumeDiffSummary(BaseModel):
    total_changes: int = 0
    skills_added: int = 0
    skills_removed: int = 0
    descriptions_modified: int = 0
    certifications_added: int = 0
    high_risk_changes: int = 0
class RefinementStats(BaseModel):
    initial_match_percentage: float = 0.0
    final_match_percentage: float = 0.0
class ImproveResumeData(BaseModel):
    resume_id: str | None = None
    job_id: str
    improvements: list[ImprovementSuggestion] = Field(default_factory=list)
    markdownImproved: str | None = None
    cover_letter: str | None = None
    outreach_message: str | None = None
    diff_summary: ResumeDiffSummary | None = None
    refinement_stats: RefinementStats | None = None
    warnings: list[str] = Field(default_factory=list)
class ImproveResumeResponse(BaseModel):
    request_id: str
    data: ImproveResumeData
class CareerOpsMarketSource(BaseModel):
    title: str
    url: str
    snippet: str = ""
class CareerOpsMarketData(BaseModel):
    role_query: str
    company_name: str | None = None
    salary_mentions: list[str] = Field(default_factory=list)
    demand_summary: str = ""
    compensation_summary: str = ""
    sources: list[CareerOpsMarketSource] = Field(default_factory=list)
class CareerOpsEvaluationData(BaseModel):
    overall_score: float = 0.0
    overall_label: str = ""
    executive_summary: str = ""
    archetype: str = ""
    af_scores: dict[str, float] = Field(default_factory=dict)
    dimensions: list[dict[str, Any]] = Field(default_factory=list)
    tailoring_priorities: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    keyword_targets: list[str] = Field(default_factory=list)
    market_data: CareerOpsMarketData | None = None
class CareerOpsEvaluateResponse(BaseModel):
    request_id: str
    data: CareerOpsEvaluationData
class CareerOpsScannedOffer(BaseModel):
    title: str
    url: str
    company: str
    location: str = ""
    source: str
class CareerOpsScanData(BaseModel):
    scanned_companies: int = 0
    total_jobs_found: int = 0
    filtered_out: int = 0
    duplicates: int = 0
    new_offers: list[CareerOpsScannedOffer] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
class CareerOpsScanResponse(BaseModel):
    request_id: str
    data: CareerOpsScanData
class SeekSearchPlan(BaseModel):
    resume_id: str
    source: str = "seek"
    candidate_profile_summary: str = ""
    keywords: list[str] = Field(default_factory=list)
    location: str = ""
class SeekSearchJob(BaseModel):
    job_id: str
    source: str = "seek"
    search_keyword: str
    title: str
    company: str
    location: str = ""
    salary: str | None = None
    work_type: str | None = None
    listed_at: str | None = None
    job_url: str = ""
    summary: str | None = None
    match_score: float = 0.0
class SeekSearchStats(BaseModel):
    keywords_generated: int = 0
    queries_attempted: int = 0
    queries_succeeded: int = 0
    raw_jobs_found: int = 0
    jobs_after_dedupe: int = 0
class SeekSearchError(BaseModel):
    search_keyword: str
    message: str
class SeekSearchResponse(BaseModel):
    plan: SeekSearchPlan
    jobs: list[SeekSearchJob] = Field(default_factory=list)
    stats: SeekSearchStats
    errors: list[SeekSearchError] = Field(default_factory=list)
class PortalsTitleFilter(BaseModel):
    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)
    seniority_boost: list[str] = Field(default_factory=list)
class PortalsSearchQuery(BaseModel):
    name: str
    query: str
    enabled: bool = True
class PortalsTrackedCompany(BaseModel):
    name: str
    careers_url: str
    enabled: bool = True
    api: str | None = None
    scan_method: str | None = None
    scan_query: str | None = None
    notes: str | None = None
class PortalsConfig(BaseModel):
    title_filter: PortalsTitleFilter = Field(default_factory=PortalsTitleFilter)
    search_queries: list[PortalsSearchQuery] = Field(default_factory=list)
    tracked_companies: list[PortalsTrackedCompany] = Field(default_factory=list)
class MultilingualResumeAssets(BaseModel):
    candidate_id: str = "default"
    resume_en_id: str | None = None
    resume_ja_id: str | None = None
    resume_zh_id: str | None = None
    updated_at: str | None = None
class ScheduledScanConfig(BaseModel):
    enabled: bool = False
    run_time_local: str = "09:00"
    timezone: str = "Australia/Sydney"
    seek_enabled: bool = False
    doda_enabled: bool = False
    boss_enabled: bool = False
    feishu_enabled: bool = False
    feishu_webhook_url: str | None = None
    high_score_threshold: float = 0.75
    last_run_at: str | None = None
    last_run_date_local: str | None = None
    last_run_status: str | None = None
    last_error: str | None = None
    last_result_counts: dict[str, Any] = Field(default_factory=dict)
class DiscoveredJobRecord(BaseModel):
    job_key: str
    source: str
    resume_language: str
    title: str
    company: str
    location: str = ""
    job_url: str = ""
    summary: str | None = None
    match_score: float = 0.0
    discovered_at: str
    first_seen_at: str
    last_seen_at: str
    is_new: bool = True
    status: str = "new"
class ScheduledScanSettingsResponse(BaseModel):
    config: ScheduledScanConfig
    assets: MultilingualResumeAssets
    recent_new_jobs: list[DiscoveredJobRecord] = Field(default_factory=list)
    high_score_unapplied_jobs: list[DiscoveredJobRecord] = Field(default_factory=list)
ResumeFetchData.model_rebuild()
ResumeFetchResponse.model_rebuild()
ImproveResumeData.model_rebuild()
ImproveResumeResponse.model_rebuild()
CareerOpsEvaluationData.model_rebuild()
CareerOpsEvaluateResponse.model_rebuild()
CareerOpsScanData.model_rebuild()
CareerOpsScanResponse.model_rebuild()
SeekSearchPlan.model_rebuild()
SeekSearchJob.model_rebuild()
SeekSearchStats.model_rebuild()
SeekSearchError.model_rebuild()
SeekSearchResponse.model_rebuild()
PortalsConfig.model_rebuild()
MultilingualResumeAssets.model_rebuild()
ScheduledScanConfig.model_rebuild()
DiscoveredJobRecord.model_rebuild()
ScheduledScanSettingsResponse.model_rebuild()
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
        self.job_counter = 0
        self.job_descriptions: dict[str, str] = {}
        self.multilingual_assets = MultilingualResumeAssets(
            resume_en_id=self.resume_id,
            resume_ja_id="test-ja-resume",
            updated_at="2026-04-17T00:00:00+00:00",
        )
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
                    "last_result_counts": {},
                },
                "assets": self.multilingual_assets.model_dump(),
                "recent_new_jobs": [],
                "high_score_unapplied_jobs": [],
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
                        "# Tailored Resume\n\n"
                        f"Optimized for: {job_description[:120]}\n\n"
                        "- Python\n- FastAPI\n- Delivery impact\n"
                    )
                    if include_resume_id
                    else None,
                    "cover_letter": "Short targeted cover letter." if include_resume_id else None,
                    "outreach_message": "Hi, I would love to discuss the role."
                    if include_resume_id
                    else None,
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
                    "resume_id": self.multilingual_assets.resume_ja_id or "test-ja-resume",
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
        jobs = list(self.scheduled_scan_settings.high_score_unapplied_jobs) + list(
            self.scheduled_scan_settings.recent_new_jobs
        )
        for job in jobs:
            if job.job_key == job_key:
                return job.model_copy(update={"status": status})
        raise ValueError(f"Job not found: {job_key}")
def ensure_runtime_assets() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    auto_login_js = PUBLIC_DIR / "auto-login.js"
    if not AUTO_LOGIN_ENABLED:
        if auto_login_js.exists():
            auto_login_js.unlink()
        return
    script = f"""(function () {{
  const username = {json.dumps(APP_USERNAME)};
  const password = {json.dumps(APP_PASSWORD)};
  const attemptKey = "ai_job_mediator_auto_login_attempted";
  const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
  const rootPath =
    (document
      .querySelector('meta[property="og:root_path"]')
      ?.getAttribute("content") || "").replace(/\\/$/, "");
  const appRootUrl = window.location.origin + rootPath + "/";
  const currentPath = window.location.pathname.replace(/\\/$/, "");
  const loginPath = (rootPath || "") + "/login";
  const isLoginPage = currentPath === loginPath;
  async function autoLogin() {{
    if (!isLocalHost) return;
    try {{
      const authConfigResponse = await fetch("/auth/config", {{ credentials: "include" }});
      if (!authConfigResponse.ok) return;
      const authConfig = await authConfigResponse.json();
      if (!authConfig?.requireLogin || !authConfig?.passwordAuth) return;
      const currentUserResponse = await fetch("/user", {{ credentials: "include" }});
      if (currentUserResponse.ok) {{
        sessionStorage.removeItem(attemptKey);
        if (isLoginPage) {{
          window.location.replace(appRootUrl);
        }}
        return;
      }}
      if (!isLoginPage) {{
        sessionStorage.removeItem(attemptKey);
        return;
      }}
      if (sessionStorage.getItem(attemptKey) === "1") return;
      sessionStorage.setItem(attemptKey, "1");
      await fetch("/logout", {{
        method: "POST",
        credentials: "include",
      }}).catch(() => null);
      const form = new URLSearchParams();
      form.set("username", username);
      form.set("password", password);
      const loginResponse = await fetch("/login", {{
        method: "POST",
        credentials: "include",
        headers: {{
          "Content-Type": "application/x-www-form-urlencoded",
        }},
        body: form.toString(),
      }});
      if (!loginResponse.ok) {{
        sessionStorage.removeItem(attemptKey);
        return;
      }}
      sessionStorage.removeItem(attemptKey);
      window.location.replace(appRootUrl);
    }} catch (error) {{
      sessionStorage.removeItem(attemptKey);
      console.warn("Local auto-login failed.", error);
    }}
  }}
  autoLogin();
}})();
"""
    auto_login_js.write_text(script, encoding="utf-8")
ensure_runtime_assets()
backend: ResumeMatcherBackend | InMemoryTestBackend
if TEST_MODE_ENABLED:
    backend = InMemoryTestBackend()
    data_layer = LocalJsonDataLayer(
        data_dir=DATA_DIR,
        public_dir=PUBLIC_DIR,
    )
else:
    backend = ResumeMatcherBackend(BACKEND_URL)
    data_layer = BackendTinyDBDataLayer(
        base_url=BACKEND_URL,
        data_dir=DATA_DIR,
        public_dir=PUBLIC_DIR,
    )
def apply_thread_metadata_to_session(
    thread: ThreadDict | dict[str, Any] | None,
    session: Any | None = None,
) -> bool:
    if not thread:
        return False
    metadata = thread.get("metadata") or {}
    if not metadata:
        return False
    active_session = session or cl.user_session
    active_session.set(SESSION_RESUME_ID, metadata.get(SESSION_RESUME_ID))
    active_session.set(SESSION_RESUME_STATUS, metadata.get(SESSION_RESUME_STATUS))
    active_session.set(SESSION_LAST_UPLOAD_NAME, metadata.get(SESSION_LAST_UPLOAD_NAME))
    active_session.set(
        SESSION_LAST_TAILORED_RESUME_ID,
        metadata.get(SESSION_LAST_TAILORED_RESUME_ID),
    )
    active_session.set(
        SESSION_LAST_JOB_DESCRIPTION,
        metadata.get(SESSION_LAST_JOB_DESCRIPTION),
    )
    active_session.set(
        SESSION_THREAD_NAMED,
        metadata.get(SESSION_THREAD_NAMED, bool(thread.get("name"))),
    )
    return True
async def sync_thread_metadata(*, clear_thread_name: bool = False) -> None:
    thread_id = getattr(context.session, "thread_id", None)
    if not thread_id:
        return
    await data_layer.update_thread(
        thread_id=thread_id,
        name="" if clear_thread_name else None,
        user_id=get_current_user_id(),
        metadata={
            SESSION_RESUME_ID: cl.user_session.get(SESSION_RESUME_ID),
            SESSION_RESUME_STATUS: cl.user_session.get(SESSION_RESUME_STATUS),
            SESSION_LAST_UPLOAD_NAME: cl.user_session.get(SESSION_LAST_UPLOAD_NAME),
            SESSION_LAST_TAILORED_RESUME_ID: cl.user_session.get(
                SESSION_LAST_TAILORED_RESUME_ID
            ),
            SESSION_LAST_JOB_DESCRIPTION: cl.user_session.get(
                SESSION_LAST_JOB_DESCRIPTION
            ),
            SESSION_THREAD_NAMED: cl.user_session.get(SESSION_THREAD_NAMED),
        },
    )
async def restore_session_from_current_thread() -> bool:
    thread_id = getattr(context.session, "thread_id", None)
    if not thread_id:
        return False
    thread = await data_layer.get_thread(thread_id)
    return apply_thread_metadata_to_session(thread)
async def remember_job_description(job_description: str) -> None:
    cl.user_session.set(SESSION_LAST_JOB_DESCRIPTION, job_description)
    await sync_thread_metadata()
def get_current_user_id() -> str | None:
    session = getattr(context, "session", None)
    user = getattr(session, "user", None)
    user_id = getattr(user, "id", None)
    return str(user_id) if user_id else None
def normalize_text(text: str) -> str:
    return text.strip().casefold()
def resolve_mime_type(file_name: str, reported_mime: str | None = None) -> str:
    if reported_mime in SUPPORTED_MIME_TYPES:
        return reported_mime
    extension = Path(file_name).suffix.lower()
    if extension in SUPPORTED_EXTENSIONS:
        return SUPPORTED_EXTENSIONS[extension]
    guessed, _ = mimetypes.guess_type(file_name)
    if guessed in SUPPORTED_MIME_TYPES:
        return guessed
    raise ValueError("目前只支持 PDF、DOC 和 DOCX 简历文件。")
def extract_supported_files(elements: list[Any] | None) -> list[Any]:
    if not elements:
        return []
    supported: list[Any] = []
    for element in elements:
        name = getattr(element, "name", "") or ""
        mime_type = getattr(element, "mime", None) or getattr(element, "type", None)
        extension = Path(name).suffix.lower()
        if mime_type in SUPPORTED_MIME_TYPES or extension in SUPPORTED_EXTENSIONS:
            supported.append(element)
    return supported
def is_analysis_request(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    return any(keyword in normalized for keyword in ANALYSIS_KEYWORDS)
def is_career_ops_evaluate_request(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    return any(keyword in normalized for keyword in EVALUATE_KEYWORDS)
def is_optimize_request(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    return any(keyword in normalized for keyword in OPTIMIZE_KEYWORDS)
def is_scan_request(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    return any(keyword in normalized for keyword in SCAN_KEYWORDS)
def is_portals_view_request(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    return any(keyword in normalized for keyword in PORTALS_VIEW_KEYWORDS)
def is_portals_edit_request(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    return any(keyword in normalized for keyword in PORTALS_EDIT_KEYWORDS)
def is_scheduled_scan_view_request(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    return any(keyword in normalized for keyword in SCHEDULED_SCAN_VIEW_KEYWORDS)
def is_scheduled_scan_edit_request(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    return any(keyword in normalized for keyword in SCHEDULED_SCAN_EDIT_KEYWORDS)
def looks_like_job_description(user_text: str) -> bool:
    normalized = normalize_text(user_text)
    marker_hits = sum(1 for marker in JD_MARKERS if marker in normalized)
    return marker_hits >= 2 or len(user_text.strip()) >= 300
def build_general_reply(user_text: str) -> str:
    normalized = normalize_text(user_text)
    if any(token in normalized for token in ("职位", "岗位", "方向", "career", "role")):
        return (
            "可以，我们先把目标收窄一点会更高效。"
            "你现在可以直接贴一个 JD，我来帮你做匹配分析；"
            "或者告诉我你想冲的方向，我会先帮你梳理适合的岗位画像。"
        )
    return (
        f"我在这边。现在最适合直接往前推进的做法是：贴一个目标 JD，"
        "我帮你先看匹配度、强项和缺失关键词；如果你已经有目标岗位，"
        f"我就基于当前后端模型配置 `{LLM_MODEL}` 帮你走简历优化。"
    )
def format_analysis_result(result: ImproveResumeResponse) -> str:
    summary = result.data.diff_summary
    refinement = result.data.refinement_stats
    suggestions = result.data.improvements[:5]
    lines = [
        "### 职位匹配分析",
        "",
        "我已经根据这份 JD 做了一轮快速匹配，先把最关键的结论给你：",
    ]
    if refinement:
        lines.extend(
            [
                "",
                f"- 初始匹配度：`{refinement.initial_match_percentage:.1f}%`",
                f"- 优化后潜在匹配度：`{refinement.final_match_percentage:.1f}%`",
            ]
        )
    if summary:
        lines.extend(
            [
                f"- 预计需要调整的内容：`{summary.total_changes}` 处",
                f"- 可补强的技能关键词：`{summary.skills_added}` 项",
                f"- 建议重写的经历描述：`{summary.descriptions_modified}` 条",
            ]
        )
    if suggestions:
        lines.extend(["", "### 我建议优先处理的点"])
        for item in suggestions:
            lines.append(f"- {item.suggestion}")
    if result.data.warnings:
        lines.extend(["", "### 需要注意"])
        for warning in result.data.warnings[:3]:
            lines.append(f"- {warning}")
    lines.extend(
        [
            "",
            "如果你愿意，我下一步可以直接按这份 JD 帮你生成一版优化后的简历内容。",
        ]
    )
    return "\n".join(lines)
def format_optimization_result(result: ImproveResumeResponse) -> str:
    summary = result.data.diff_summary
    suggestions = result.data.improvements[:5]
    resume_id = result.data.resume_id or "未返回"
    lines = [
        "### 简历优化完成",
        "",
        f"- 新生成的 tailored resume_id：`{resume_id}`",
    ]
    if summary:
        lines.extend(
            [
                f"- 总调整项：`{summary.total_changes}`",
                f"- 新增技能关键词：`{summary.skills_added}`",
                f"- 重写经历描述：`{summary.descriptions_modified}`",
            ]
        )
    if suggestions:
        lines.extend(["", "### 这版改动的重点"])
        for item in suggestions:
            lines.append(f"- {item.suggestion}")
    lines.extend(
        [
            "",
            "我把可下载的文本文件一起挂在下面了，你可以直接打开或继续让我二次修改。",
        ]
    )
    return "\n".join(lines)
def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()
def render_portals_config(config: PortalsConfig | dict[str, Any]) -> str:
    payload = (
        config.model_dump(exclude_none=True)
        if isinstance(config, BaseModel)
        else dict(config)
    )
    return yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
def render_scheduled_scan_config(config: ScheduledScanConfig | dict[str, Any]) -> str:
    payload = (
        config.model_dump(exclude_none=True)
        if isinstance(config, BaseModel)
        else dict(config)
    )
    return yaml.safe_dump(
        payload,
        sort_keys=False,
        allow_unicode=True,
        default_flow_style=False,
    ).strip()
def parse_portals_config_input(text: str) -> dict[str, Any]:
    cleaned = strip_code_fence(text)
    loaded = yaml.safe_load(cleaned)
    if not isinstance(loaded, dict):
        raise ValueError("Portals 配置必须是一个 YAML 或 JSON 对象。")
    return loaded
def parse_scheduled_scan_config_input(text: str) -> dict[str, Any]:
    cleaned = strip_code_fence(text)
    loaded = yaml.safe_load(cleaned)
    if not isinstance(loaded, dict):
        raise ValueError("自动扫描设置必须是一个 YAML 或 JSON 对象。")
    return loaded
def parse_scheduled_scan_field_input(field: str, text: str) -> Any:
    cleaned = strip_code_fence(text).strip()
    if field == "run_time_local":
        value = cleaned.split("=")[-1].strip().strip("'\"")
        parts = value.split(":")
        if len(parts) != 2 or not all(part.isdigit() for part in parts):
            raise ValueError("时间格式需要是 HH:MM，例如 21:30。")
        hour, minute = [int(part) for part in parts]
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("时间必须落在 00:00 到 23:59 之间。")
        return f"{hour:02d}:{minute:02d}"
    if field == "high_score_threshold":
        value = cleaned.split("=")[-1].strip()
        threshold = float(value)
        if not (0.0 <= threshold <= 1.0):
            raise ValueError("阈值需要在 0.0 到 1.0 之间。")
        return threshold
    if field == "feishu_webhook_url":
        value = cleaned.split("=", 1)[-1].strip()
        if value.lower() in {"none", "null", "clear", "empty"}:
            return None
        return value or None
    raise ValueError(f"不支持的自动扫描字段：{field}")
def format_scheduled_scan_settings(result: ScheduledScanSettingsResponse) -> str:
    config = result.config
    assets = result.assets
    recent_jobs = result.recent_new_jobs[:5]
    lines = [
        "### 自动扫描设置",
        "",
        f"- 启用状态：`{'开启' if config.enabled else '关闭'}`",
        f"- 每天执行时间：`{config.run_time_local}`",
        f"- 时区：`{config.timezone}`",
        f"- 上次运行状态：`{config.last_run_status or '未运行'}`",
    ]
    if config.last_run_at:
        lines.append(f"- 上次运行时间：`{config.last_run_at}`")
    if config.last_error:
        lines.append(f"- 最近错误：{config.last_error}")
    lines.extend(
        [
            "",
            "### 多语言简历状态",
            f"- 英文简历 / SEEK：`{'已上传' if assets.resume_en_id else '未上传'}` / `{'开启' if config.seek_enabled else '关闭'}`",
            f"- 日文简历 / doda：`{'已上传' if assets.resume_ja_id else '未上传'}` / `{'开启' if config.doda_enabled else '关闭'}`",
            f"- 中文简历 / BOSS直聘：`{'已上传' if assets.resume_zh_id else '未上传'}` / `{'开启' if config.boss_enabled else '关闭'}`",
            f"- 飞书通知：`{'开启' if config.feishu_enabled else '关闭'}`",
        ]
    )
    if config.feishu_webhook_url:
        lines.append(f"- 飞书 Webhook：`{config.feishu_webhook_url}`")
    lines.append(f"- 高分阈值：`{config.high_score_threshold:.2f}`")
    if config.last_result_counts:
        lines.extend(["", "### 最近一次扫描统计"])
        for source, counts in config.last_result_counts.items():
            raw_jobs = counts.get("raw_jobs_found", 0)
            new_jobs = counts.get("new_jobs", 0)
            lines.append(f"- {source.upper()}：抓到 `{raw_jobs}` 条，本次新增 `{new_jobs}` 条")
    if recent_jobs:
        lines.extend(["", "### 最近新增岗位"])
        for job in recent_jobs:
            score = f"{job.match_score:.2f}"
            location = f" | {job.location}" if job.location else ""
            lines.append(
                f"- {job.title} | {job.company}{location} | {job.source.upper()} | score `{score}` | status `{job.status}`"
            )
    else:
        lines.extend(["", "最近还没有新增岗位记录。"])
    if result.high_score_unapplied_jobs:
        lines.extend(["", "### 高分未投递岗位"])
        for job in result.high_score_unapplied_jobs[:5]:
            score = f"{job.match_score:.2f}"
            location = f" | {job.location}" if job.location else ""
            lines.append(
                f"- {job.title} | {job.company}{location} | {job.source.upper()} | score `{score}` | status `{job.status}`"
            )
    return "\n".join(lines)
def format_career_ops_evaluation(result: CareerOpsEvaluateResponse) -> str:
    data = result.data
    lines = [
        "### A-F 职位评估",
        "",
        f"- 综合评分：`{data.overall_score:.1f}/5.0`",
        f"- 结论：`{data.overall_label}`",
        f"- 画像：`{data.archetype}`",
        "",
        data.executive_summary,
    ]
    if data.af_scores:
        lines.extend(["", "### A-F 分项分数"])
        for key in ("A", "B", "C", "D", "E", "F"):
            if key in data.af_scores:
                lines.append(f"- {key}：`{data.af_scores[key]:.1f}`")
    if data.tailoring_priorities:
        lines.extend(["", "### 定向优化重点"])
        for item in data.tailoring_priorities[:5]:
            lines.append(f"- {item}")
    if data.interview_focus:
        lines.extend(["", "### 面试建议重点"])
        for item in data.interview_focus[:5]:
            lines.append(f"- {item}")
    if data.keyword_targets:
        lines.extend(
            [
                "",
                "### 关键词目标",
                f"- {', '.join(data.keyword_targets[:10])}",
            ]
        )
    market = data.market_data
    if market:
        lines.extend(["", "### 市场信号"])
        if market.compensation_summary:
            lines.append(f"- 薪酬观察：{market.compensation_summary}")
        if market.demand_summary:
            lines.append(f"- 需求观察：{market.demand_summary}")
        if market.salary_mentions:
            lines.append(f"- 薪资片段：{', '.join(market.salary_mentions[:5])}")
        if market.sources:
            lines.extend(["", "### 参考来源"])
            for source in market.sources[:5]:
                label = source.title or source.url
                snippet = f" - {source.snippet}" if source.snippet else ""
                lines.append(f"- [{label}]({source.url}){snippet}")
    return "\n".join(lines)
def format_scan_result(result: CareerOpsScanResponse) -> str:
    data = result.data
    lines = [
        "### 职位扫描结果",
        "",
        f"- 扫描公司数：`{data.scanned_companies}`",
        f"- 抓到职位数：`{data.total_jobs_found}`",
        f"- 过滤掉的职位：`{data.filtered_out}`",
        f"- 去重数量：`{data.duplicates}`",
    ]
    if data.new_offers:
        lines.extend(["", "### 新发现职位"])
        for offer in data.new_offers[:10]:
            location = f" | {offer.location}" if offer.location else ""
            lines.append(
                f"- [{offer.title}]({offer.url}) | {offer.company}{location} | {offer.source}"
            )
    else:
        lines.extend(["", "这次没有发现新的职位。"])
    if data.errors:
        lines.extend(["", "### 扫描告警"])
        for error in data.errors[:5]:
            lines.append(f"- {error}")
    return "\n".join(lines)
def format_seek_search_result(result: SeekSearchResponse) -> str:
    plan = result.plan
    stats = result.stats
    source_label = "SEEK" if plan.source == "seek" else plan.source
    lines = [
        f"### {source_label} 搜索结果",
        "",
        f"- 地点：`{plan.location}`",
        f"- 关键词：{', '.join(plan.keywords)}",
        f"- 原始岗位数：`{stats.raw_jobs_found}`",
        f"- 去重后岗位数：`{stats.jobs_after_dedupe}`",
    ]
    if result.jobs:
        lines.extend(["", "### 推荐岗位"])
        for job in result.jobs[:10]:
            extras = []
            if job.salary:
                extras.append(job.salary)
            if job.work_type:
                extras.append(job.work_type)
            if job.listed_at:
                extras.append(job.listed_at)
            extra_text = f" | {' | '.join(extras)}" if extras else ""
            lines.append(
                f"- [{job.title}]({job.job_url}) | {job.company} | {job.location} | 匹配分 `{job.match_score:.2f}`{extra_text}"
            )
    else:
        lines.extend(["", "这次没有抓到符合条件的 SEEK 岗位。"])
    if result.errors:
        lines.extend(["", "### 查询告警"])
        for error in result.errors[:5]:
            lines.append(f"- `{error.search_keyword}`: {error.message}")
    return "\n".join(lines)
def format_portals_summary(config: PortalsConfig) -> str:
    return (
        "### Portals 配置已就绪\n\n"
        f"- 追踪公司：`{len(config.tracked_companies)}`\n"
        f"- 搜索查询：`{len(config.search_queries)}`\n"
        f"- 正向标题词：`{len(config.title_filter.positive)}`"
    )
def build_tool_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name=ACTION_REUPLOAD_MASTER_RESUME,
            payload={"feature": ACTION_REUPLOAD_MASTER_RESUME},
            label="重新上传主简历",
            tooltip="再次上传会直接更新当前主简历",
        ),
        cl.Action(
            name=ACTION_EVALUATE_JOB,
            payload={"feature": ACTION_EVALUATE_JOB},
            label="A-F 职位评估",
            tooltip="输入 JD，查看 A-F 评分和 market data",
        ),
        cl.Action(
            name=ACTION_DOWNLOAD_TAILORED_PDF,
            payload={"feature": ACTION_DOWNLOAD_TAILORED_PDF},
            label="下载 ATS PDF",
            tooltip="用当前主简历和目标 JD 生成 ATS 友好 PDF",
        ),
        cl.Action(
            name=ACTION_SCAN_JOBS,
            payload={"feature": ACTION_SCAN_JOBS},
            label="扫描职位",
            tooltip="从配置好的 portals 拉取新职位",
        ),
        cl.Action(
            name=ACTION_SEARCH_SEEK,
            payload={"feature": ACTION_SEARCH_SEEK},
            label="SEEK 搜索岗位",
            tooltip="根据当前简历生成关键词并搜索 SEEK 列表页",
        ),
        cl.Action(
            name=ACTION_SEARCH_DODA,
            payload={"feature": ACTION_SEARCH_DODA},
            label="doda 搜索岗位",
            tooltip="根据当前日文简历生成关键词并搜索 doda 列表页",
        ),
        cl.Action(
            name=ACTION_VIEW_PORTALS,
            payload={"feature": ACTION_VIEW_PORTALS},
            label="查看 Portals",
            tooltip="查看当前 portals 配置",
        ),
        cl.Action(
            name=ACTION_EDIT_PORTALS,
            payload={"feature": ACTION_EDIT_PORTALS},
            label="更新 Portals",
            tooltip="贴 YAML/JSON 直接更新 portals 配置",
        ),
        cl.Action(
            name=ACTION_DELETE_CURRENT_THREAD,
            payload={"feature": ACTION_DELETE_CURRENT_THREAD},
            label="删除当前对话",
            tooltip="清空这条对话历史，后续消息重新开始记录",
        ),
    ]
async def send_tool_actions() -> None:
    await cl.Message(
        content="也可以直接点这些常用功能：",
        actions=build_tool_actions(),
    ).send()
def build_tool_actions() -> list[cl.Action]:
    return [
        cl.Action(
            name=ACTION_REUPLOAD_MASTER_RESUME,
            payload={"feature": ACTION_REUPLOAD_MASTER_RESUME},
            label="重新上传主简历",
            tooltip="重新上传英文主简历并覆盖当前默认版本",
        ),
        cl.Action(
            name=ACTION_EVALUATE_JOB,
            payload={"feature": ACTION_EVALUATE_JOB},
            label="A-F 职位评估",
            tooltip="输入 JD，查看 A-F 评分和 market data",
        ),
        cl.Action(
            name=ACTION_DOWNLOAD_TAILORED_PDF,
            payload={"feature": ACTION_DOWNLOAD_TAILORED_PDF},
            label="下载 ATS PDF",
            tooltip="用当前主简历和目标 JD 生成 ATS 友好 PDF",
        ),
        cl.Action(
            name=ACTION_SCAN_JOBS,
            payload={"feature": ACTION_SCAN_JOBS},
            label="扫描职位",
            tooltip="从配置好的 portals 拉取新职位",
        ),
        cl.Action(
            name=ACTION_SEARCH_SEEK,
            payload={"feature": ACTION_SEARCH_SEEK},
            label="SEEK 搜索岗位",
            tooltip="根据当前英文简历生成关键词并搜索 SEEK 列表页",
        ),
        cl.Action(
            name=ACTION_SEARCH_DODA,
            payload={"feature": ACTION_SEARCH_DODA},
            label="doda 搜索岗位",
            tooltip="根据当前日文简历生成关键词并搜索 doda 列表页",
        ),
        cl.Action(
            name=ACTION_UPLOAD_EN_RESUME,
            payload={"feature": ACTION_UPLOAD_EN_RESUME},
            label="上传英文简历",
            tooltip="上传英文简历并绑定到 SEEK",
        ),
        cl.Action(
            name=ACTION_UPLOAD_JA_RESUME,
            payload={"feature": ACTION_UPLOAD_JA_RESUME},
            label="上传日文简历",
            tooltip="上传日文简历并为 doda 预留",
        ),
        cl.Action(
            name=ACTION_UPLOAD_ZH_RESUME,
            payload={"feature": ACTION_UPLOAD_ZH_RESUME},
            label="上传中文简历",
            tooltip="上传中文简历并为 BOSS直聘 预留",
        ),
        cl.Action(
            name=ACTION_VIEW_PORTALS,
            payload={"feature": ACTION_VIEW_PORTALS},
            label="查看 Portals",
            tooltip="查看当前 portals 配置",
        ),
        cl.Action(
            name=ACTION_EDIT_PORTALS,
            payload={"feature": ACTION_EDIT_PORTALS},
            label="更新 Portals",
            tooltip="贴 YAML/JSON 直接更新 portals 配置",
        ),
        cl.Action(
            name=ACTION_VIEW_SCHEDULED_SCAN,
            payload={"feature": ACTION_VIEW_SCHEDULED_SCAN},
            label="查看自动扫描",
            tooltip="查看当前多语言简历状态和自动扫描设置",
        ),
        cl.Action(
            name=ACTION_EDIT_SCHEDULED_SCAN,
            payload={"feature": ACTION_EDIT_SCHEDULED_SCAN},
            label="更新自动扫描",
            tooltip="贴 YAML/JSON 直接更新自动扫描设置",
        ),
        cl.Action(
            name=ACTION_DELETE_CURRENT_THREAD,
            payload={"feature": ACTION_DELETE_CURRENT_THREAD},
            label="删除当前对话",
            tooltip="清空这条对话历史，后续消息重新开始记录",
        ),
    ]
def build_discovered_job_actions(
    jobs: list[DiscoveredJobRecord],
) -> list[cl.Action]:
    actions: list[cl.Action] = []
    for job in jobs[:5]:
        if job.status == "applied":
            continue
        actions.append(
            cl.Action(
                name=ACTION_MARK_JOB_APPLIED,
                payload={"job_key": job.job_key, "status": "applied"},
                label=f"标记已投递: {job.company}",
                tooltip=f"把 {job.title} 标记为已投递",
            )
        )
    return actions
def build_scheduled_scan_form_actions(
    config: ScheduledScanConfig,
) -> list[cl.Action]:
    return [
        cl.Action(
            name=ACTION_TOGGLE_SCHEDULED_SCAN_FIELD,
            payload={"field": "enabled", "value": not config.enabled},
            label="关闭自动扫描" if config.enabled else "开启自动扫描",
            tooltip="切换每日自动扫描总开关",
        ),
        cl.Action(
            name=ACTION_PROMPT_SCHEDULED_SCAN_FIELD,
            payload={"field": "run_time_local"},
            label="设置时间",
            tooltip="修改每日执行时间",
        ),
        cl.Action(
            name=ACTION_PROMPT_SCHEDULED_SCAN_FIELD,
            payload={"field": "high_score_threshold"},
            label="设置阈值",
            tooltip="修改高分岗位通知阈值",
        ),
        cl.Action(
            name=ACTION_TOGGLE_SCHEDULED_SCAN_FIELD,
            payload={"field": "seek_enabled", "value": not config.seek_enabled},
            label="关闭 SEEK" if config.seek_enabled else "开启 SEEK",
            tooltip="切换 SEEK 自动扫描",
        ),
        cl.Action(
            name=ACTION_TOGGLE_SCHEDULED_SCAN_FIELD,
            payload={"field": "doda_enabled", "value": not config.doda_enabled},
            label="关闭 doda" if config.doda_enabled else "开启 doda",
            tooltip="切换 doda 自动扫描",
        ),
        cl.Action(
            name=ACTION_TOGGLE_SCHEDULED_SCAN_FIELD,
            payload={"field": "boss_enabled", "value": not config.boss_enabled},
            label="关闭 BOSS直聘" if config.boss_enabled else "开启 BOSS直聘",
            tooltip="切换 BOSS直聘 自动扫描",
        ),
        cl.Action(
            name=ACTION_TOGGLE_SCHEDULED_SCAN_FIELD,
            payload={"field": "feishu_enabled", "value": not config.feishu_enabled},
            label="关闭飞书通知" if config.feishu_enabled else "开启飞书通知",
            tooltip="切换飞书 webhook 通知",
        ),
        cl.Action(
            name=ACTION_PROMPT_SCHEDULED_SCAN_FIELD,
            payload={"field": "feishu_webhook_url"},
            label="设置飞书 Webhook",
            tooltip="修改飞书通知 webhook 地址",
        ),
    ]
def build_download_elements(result: ImproveResumeResponse) -> list[cl.File]:
    elements: list[cl.File] = []
    if result.data.markdownImproved:
        elements.append(
            cl.File(
                name="tailored_resume.md",
                content=result.data.markdownImproved.encode("utf-8"),
                display="inline",
                mime="text/markdown",
            )
        )
    if result.data.cover_letter:
        elements.append(
            cl.File(
                name="cover_letter.md",
                content=result.data.cover_letter.encode("utf-8"),
                display="inline",
                mime="text/markdown",
            )
        )
    if result.data.outreach_message:
        elements.append(
            cl.File(
                name="outreach_message.md",
                content=result.data.outreach_message.encode("utf-8"),
                display="inline",
                mime="text/markdown",
            )
        )
    return elements
def build_pdf_download_element(pdf_payload: dict[str, Any]) -> cl.File:
    return cl.File(
        name=pdf_payload["filename"],
        content=pdf_payload["content"],
        display="inline",
        mime="application/pdf",
    )
async def ensure_resume_ready(resume_id: str) -> bool:
    status = await backend.get_resume_status(resume_id)
    cl.user_session.set(SESSION_RESUME_STATUS, status)
    await sync_thread_metadata()
    return status == "ready"
def get_resume_language_label(resume_language: str) -> str:
    return {
        "en": "英文",
        "ja": "日文",
        "zh": "中文",
    }.get(resume_language, resume_language)
async def process_resume_upload(file_obj: Any, resume_language: str = "en") -> None:
    file_path = getattr(file_obj, "path", None)
    file_name = getattr(file_obj, "name", None)
    if not file_path or not file_name:
        raise ValueError("没有拿到可用的上传文件。")
    mime_type = resolve_mime_type(
        file_name=file_name,
        reported_mime=getattr(file_obj, "mime", None) or getattr(file_obj, "type", None),
    )
    upload_result = await backend.upload_resume(
        file_path,
        file_name,
        mime_type,
        resume_language=resume_language,
    )
    if resume_language == "en":
        cl.user_session.set(SESSION_RESUME_ID, upload_result.resume_id)
        cl.user_session.set(SESSION_RESUME_STATUS, upload_result.processing_status)
        cl.user_session.set(SESSION_LAST_TAILORED_RESUME_ID, None)
        await sync_thread_metadata(
            clear_thread_name=not cl.user_session.get(SESSION_THREAD_NAMED)
        )
    cl.user_session.set(SESSION_LAST_UPLOAD_NAME, file_name)
    if resume_language == "en":
        await cl.Message(content=UPLOAD_SUCCESS_MESSAGE).send()
    else:
        await cl.Message(
            content=f"{get_resume_language_label(resume_language)}简历上传成功，后续会用于对应站点的搜索与投递。",
        ).send()
    await send_tool_actions()
async def get_resume_id_from_session() -> str | None:
    resume_id = cl.user_session.get(SESSION_RESUME_ID)
    if resume_id:
        return resume_id
    restored = await restore_session_from_current_thread()
    if restored:
        return cl.user_session.get(SESSION_RESUME_ID)
    return None
async def ensure_resume_available() -> str | None:
    resume_id = await get_resume_id_from_session()
    if resume_id:
        return resume_id
    await cl.Message(
        content="先把主简历上传给我吧。上传后我就能继续帮你做评估或优化。",
    ).send()
    return None
async def ensure_resume_available_for_language(resume_language: str) -> str | None:
    if resume_language == "en":
        return await ensure_resume_available()
    settings = await backend.get_scheduled_scan_settings()
    resume_id = getattr(settings.assets, f"resume_{resume_language}_id", None)
    if resume_id:
        return resume_id
    language_label = get_resume_language_label(resume_language)
    await cl.Message(
        content=f"请先上传{language_label}简历。上传后我就能继续帮你搜索对应站点的岗位。",
        actions=build_tool_actions(),
    ).send()
    return None
async def ask_for_resume_upload(
    prompt: str | None = None,
    resume_language: str = "en",
) -> None:
    files = await cl.AskFileMessage(
        content=prompt or "请上传你的主简历（PDF、DOC 或 DOCX）。",
        accept=FILE_ACCEPT_CONFIG,
        max_size_mb=8,
        max_files=1,
        timeout=300,
        raise_on_timeout=False,
    ).send()
    if files:
        await process_resume_upload(files[0], resume_language=resume_language)
    else:
        await cl.Message(
            content="还没有收到简历文件。你随时上传后，我就可以继续帮你处理。",
        ).send()
async def handle_career_ops_evaluation(user_text: str, resume_id: str) -> None:
    if not looks_like_job_description(user_text):
        cl.user_session.set(SESSION_PENDING_ACTION, PENDING_EVALUATE_JOB)
        await cl.Message(
            content="把目标 JD 直接贴给我，我会返回 A-F 评分、优化重点，以及最新 market data。",
            actions=build_tool_actions(),
        ).send()
        return
    if not await ensure_resume_ready(resume_id):
        await cl.Message(
            content="你的主简历还没处理完成。等状态变成 ready 后，我就能继续做 A-F 职位评估。",
        ).send()
        return
    resume_content = await backend.get_resume_content(resume_id)
    if not resume_content:
        raise ValueError("没有拿到可用于评估的简历内容。")
    progress = cl.Message(content="我正在跑 A-F 职位评估，并补市场信号，请稍等...")
    await progress.send()
    await remember_job_description(user_text)
    result = await backend.evaluate_job(resume_content, user_text)
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    progress.content = format_career_ops_evaluation(result)
    progress.actions = build_tool_actions()
    await progress.update()
async def handle_scan_request() -> None:
    progress = cl.Message(content="我正在扫描配置好的职位源，请稍等...")
    await progress.send()
    result = await backend.scan_jobs()
    progress.content = format_scan_result(result)
    progress.actions = build_tool_actions()
    await progress.update()
async def handle_seek_search_request() -> None:
    resume_id = await ensure_resume_available()
    if not resume_id:
        return
    progress = cl.Message(content="正在搜索 SEEK 岗位，请稍等...")
    await progress.send()
    result = await backend.search_seek_jobs(resume_id)
    progress.content = format_seek_search_result(result)
    progress.actions = build_tool_actions()
    await progress.update()
async def handle_doda_search_request() -> None:
    resume_id = await ensure_resume_available_for_language("ja")
    if not resume_id:
        return
    progress = cl.Message(content="正在搜索 doda 岗位，请稍等...")
    await progress.send()
    result = await backend.search_doda_jobs(resume_id)
    progress.content = format_seek_search_result(result)
    progress.actions = build_tool_actions()
    await progress.update()
async def handle_view_portals_request() -> None:
    config = await backend.get_portals_config()
    content = (
        f"{format_portals_summary(config)}\n\n"
        "```yaml\n"
        f"{render_portals_config(config)}\n"
        "```"
    )
    await cl.Message(content=content, actions=build_tool_actions()).send()
async def handle_start_portals_update() -> None:
    config = await backend.get_portals_config()
    cl.user_session.set(SESSION_PENDING_ACTION, PENDING_UPDATE_PORTALS)
    await cl.Message(
        content=(
            "把更新后的 portals YAML/JSON 直接贴给我，我会先校验再保存。\n\n"
            "当前配置：\n"
            "```yaml\n"
            f"{render_portals_config(config)}\n"
            "```"
        ),
        actions=build_tool_actions(),
    ).send()
async def handle_portals_update_submission(user_text: str) -> None:
    payload = parse_portals_config_input(user_text)
    validated = PortalsConfig.model_validate(payload)
    saved = await backend.update_portals_config(
        validated.model_dump(exclude_none=True)
    )
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    await cl.Message(
        content=(
            f"{format_portals_summary(saved)}\n\n"
            "```yaml\n"
            f"{render_portals_config(saved)}\n"
            "```"
        ),
        actions=build_tool_actions(),
    ).send()
async def handle_view_scheduled_scan_settings() -> None:
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    result = await backend.get_scheduled_scan_settings()
    content = (
        f"{format_scheduled_scan_settings(result)}\n\n"
        "```yaml\n"
        f"{render_scheduled_scan_config(result.config)}\n"
        "```"
    )
    await cl.Message(
        content=content,
        actions=build_tool_actions()
        + build_scheduled_scan_form_actions(result.config)
        + build_discovered_job_actions(result.high_score_unapplied_jobs),
    ).send()

async def handle_start_scheduled_scan_update() -> None:
    result = await backend.get_scheduled_scan_settings()
    cl.user_session.set(SESSION_PENDING_ACTION, PENDING_UPDATE_SCHEDULED_SCAN)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, True)
    await cl.Message(
        content=(
            "自动扫描设置现在支持可视化编辑：你可以直接点下面的开关，或设置时间、阈值和飞书 Webhook。\n\n"
            "如果你更习惯一次性粘贴配置，我也仍然支持 YAML/JSON。\n\n"
            "当前设置：\n"
            "```yaml\n"
            f"{render_scheduled_scan_config(result.config)}\n"
            "```"
        ),
        actions=build_tool_actions() + build_scheduled_scan_form_actions(result.config),
    ).send()
    await build_scheduled_scan_chat_settings(result.config, result.assets).send()
async def handle_scheduled_scan_update_submission(user_text: str) -> None:
    edit_field = cl.user_session.get(SESSION_SCHEDULED_SCAN_EDIT_FIELD)
    if edit_field:
        current = await backend.get_scheduled_scan_settings()
        updated_payload = current.config.model_dump(exclude_none=True)
        updated_payload[edit_field] = parse_scheduled_scan_field_input(edit_field, user_text)
        validated = ScheduledScanConfig.model_validate(updated_payload)
    else:
        payload = parse_scheduled_scan_config_input(user_text)
        validated = ScheduledScanConfig.model_validate(payload)
    saved = await backend.update_scheduled_scan_settings(
        validated.model_dump(exclude_none=True)
    )
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    await cl.Message(
        content=(
            f"{format_scheduled_scan_settings(saved)}\n\n"
            "```yaml\n"
            f"{render_scheduled_scan_config(saved.config)}\n"
            "```"
        ),
        actions=build_tool_actions()
        + build_scheduled_scan_form_actions(saved.config)
        + build_discovered_job_actions(saved.high_score_unapplied_jobs),
    ).send()

async def handle_mark_job_applied(job_key: str) -> None:
    await backend.mark_discovered_job_status(job_key, "applied")
    await handle_view_scheduled_scan_settings()

async def handle_toggle_scheduled_scan_field(field: str, value: Any) -> None:
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    current = await backend.get_scheduled_scan_settings()
    payload = current.config.model_dump(exclude_none=True)
    payload[field] = value
    saved = await backend.update_scheduled_scan_settings(payload)
    await cl.Message(
        content=f"Updated `{field}`.",
        actions=build_tool_actions()
        + build_scheduled_scan_form_actions(saved.config)
        + build_discovered_job_actions(saved.high_score_unapplied_jobs),
    ).send()
    await handle_view_scheduled_scan_settings()

async def handle_prompt_scheduled_scan_field(field: str) -> None:
    cl.user_session.set(SESSION_PENDING_ACTION, PENDING_UPDATE_SCHEDULED_SCAN)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, field)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    prompts = {
        "run_time_local": "Reply with the new daily run time, for example `21:30`.",
        "high_score_threshold": "Reply with the new high-score threshold, for example `0.85`.",
        "feishu_webhook_url": "Reply with the Feishu webhook URL, or send `none` to clear it.",
    }
    await cl.Message(
        content=prompts.get(field, "Reply with the new value."),
        actions=build_tool_actions(),
    ).send()
async def handle_generate_tailored_pdf(
    job_description: str,
    resume_id: str,
) -> None:
    if not looks_like_job_description(job_description):
        cl.user_session.set(SESSION_PENDING_ACTION, PENDING_DOWNLOAD_TAILORED_PDF)
        await cl.Message(
            content="把目标 JD 直接贴给我，我会基于当前主简历生成 ATS 友好的 PDF。",
            actions=build_tool_actions(),
        ).send()
        return
    if not await ensure_resume_ready(resume_id):
        await cl.Message(
            content="你的主简历还没处理完成。等状态变成 ready 后，我就能继续生成 ATS PDF。",
        ).send()
        return
    await remember_job_description(job_description)
    resume_content = await backend.get_resume_content(resume_id)
    if not resume_content:
        raise ValueError("没有拿到可用于生成 PDF 的简历内容。")
    progress = cl.Message(content="我正在生成 ATS 友好的定制 PDF，请稍等...")
    await progress.send()
    pdf_payload = await backend.generate_tailored_pdf(resume_content, job_description)
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    progress.content = "ATS PDF 已生成，可以直接下载。"
    progress.elements = [build_pdf_download_element(pdf_payload)]
    progress.actions = build_tool_actions()
    await progress.update()
async def handle_analysis_request(user_text: str, resume_id: str) -> None:
    if not looks_like_job_description(user_text):
        await cl.Message(
            content=(
                "要做职位匹配分析，我还需要一份更完整的 JD。"
                "你可以直接把岗位描述贴过来，我会给你看匹配度、强项和缺失关键词。"
            )
        ).send()
        return
    if not await ensure_resume_ready(resume_id):
        await cl.Message(
            content="你的主简历还没处理完成。等状态变成 ready 后，我就能继续做 JD 匹配分析。",
        ).send()
        return
    progress = cl.Message(content="我正在分析这份 JD 和你简历的匹配情况，请稍等...")
    await progress.send()
    await remember_job_description(user_text)
    job_id = await backend.upload_job_description(resume_id, user_text)
    result = await backend.preview_resume_improvement(resume_id, job_id)
    progress.content = format_analysis_result(result)
    progress.actions = build_tool_actions()
    await progress.update()
async def handle_optimization_request(user_text: str, resume_id: str) -> None:
    if not looks_like_job_description(user_text):
        await cl.Message(
            content=(
                "要优化简历，我需要你贴一份目标岗位 JD。"
                "你把岗位描述发来后，我就直接帮你生成更贴合的版本。"
            )
        ).send()
        return
    if not await ensure_resume_ready(resume_id):
        await cl.Message(
            content="你的主简历还没处理完成。等状态变成 ready 后，我再帮你做定向优化。",
        ).send()
        return
    progress = cl.Message(content="我正在基于这份 JD 生成优化后的简历内容，请稍等...")
    await progress.send()
    await remember_job_description(user_text)
    job_id = await backend.upload_job_description(resume_id, user_text)
    result = await backend.improve_resume(resume_id, job_id)
    if result.data.resume_id:
        cl.user_session.set(SESSION_LAST_TAILORED_RESUME_ID, result.data.resume_id)
        await sync_thread_metadata()
    progress.content = format_optimization_result(result)
    progress.elements = build_download_elements(result)
    progress.actions = build_tool_actions()
    await progress.update()
@cl.data_layer
def get_data_layer() -> Any:
    return data_layer
@cl.password_auth_callback
async def password_auth_callback(username: str, password: str) -> cl.User | None:
    if username == APP_USERNAME and password == APP_PASSWORD:
        return cl.User(
            identifier=username,
            display_name=APP_DISPLAY_NAME,
            metadata={"role": "local-user"},
        )
    return None
@cl.on_chat_start
async def on_chat_start() -> None:
    cl.user_session.set(SESSION_RESUME_ID, None)
    cl.user_session.set(SESSION_RESUME_STATUS, None)
    cl.user_session.set(SESSION_LAST_UPLOAD_NAME, None)
    cl.user_session.set(SESSION_LAST_TAILORED_RESUME_ID, None)
    cl.user_session.set(SESSION_LAST_JOB_DESCRIPTION, None)
    cl.user_session.set(SESSION_THREAD_NAMED, False)
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    await cl.Message(content=WELCOME_MESSAGE).send()
    await send_tool_actions()
    await ask_for_resume_upload()
@cl.on_chat_resume
async def on_chat_resume(thread: ThreadDict) -> None:
    apply_thread_metadata_to_session(thread)
@cl.action_callback(ACTION_EVALUATE_JOB)
async def on_evaluate_job_action(_: Any) -> None:
    resume_id = await ensure_resume_available()
    if not resume_id:
        return
    cl.user_session.set(SESSION_PENDING_ACTION, PENDING_EVALUATE_JOB)
    await cl.Message(
        content="把目标 JD 直接贴给我，我会返回 A-F 评分和 market data。",
        actions=build_tool_actions(),
    ).send()
@cl.action_callback(ACTION_REUPLOAD_MASTER_RESUME)
async def on_reupload_master_resume_action(_: Any) -> None:
    await ask_for_resume_upload(
        "Please upload a new primary resume. It will replace the current primary resume."
    )

@cl.action_callback(ACTION_UPLOAD_EN_RESUME)
async def on_upload_en_resume_action(_: Any) -> None:
    await ask_for_resume_upload(
        "Please upload an English resume. It will be used for SEEK searches.",
        resume_language="en",
    )

@cl.action_callback(ACTION_UPLOAD_JA_RESUME)
async def on_upload_ja_resume_action(_: Any) -> None:
    await ask_for_resume_upload(
        "Please upload a Japanese resume. It will be linked to Japanese job sites.",
        resume_language="ja",
    )

async def handle_scheduled_scan_settings_form_update(settings: dict[str, Any]) -> None:
    current = await backend.get_scheduled_scan_settings()
    updated_payload = current.config.model_dump(exclude_none=True)
    updated_payload.update(normalize_scheduled_scan_settings_input(settings))
    validated = ScheduledScanConfig.model_validate(updated_payload)
    saved = await backend.update_scheduled_scan_settings(
        validated.model_dump(exclude_none=True)
    )
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, True)
    await cl.Message(
        content=(
            "Scheduled scan settings were saved from the form.\n\n"
            f"{format_scheduled_scan_settings(saved)}\n\n"
            "```yaml\n"
            f"{render_scheduled_scan_config(saved.config)}\n"
            "```"
        ),
        actions=build_tool_actions()
        + build_scheduled_scan_form_actions(saved.config)
        + build_discovered_job_actions(saved.high_score_unapplied_jobs),
    ).send()
    await build_scheduled_scan_chat_settings(saved.config, saved.assets).send()

@cl.action_callback(ACTION_UPLOAD_ZH_RESUME)
async def on_upload_zh_resume_action(_: Any) -> None:
    await ask_for_resume_upload(
        "Please upload a Chinese resume. It will be linked to Chinese job sites.",
        resume_language="zh",
    )
@cl.action_callback(ACTION_DOWNLOAD_TAILORED_PDF)
async def on_download_tailored_pdf_action(_: Any) -> None:
    resume_id = await ensure_resume_available()
    if not resume_id:
        return
    last_job_description = cl.user_session.get(SESSION_LAST_JOB_DESCRIPTION)
    await handle_generate_tailored_pdf(last_job_description or "", resume_id)
@cl.action_callback(ACTION_SCAN_JOBS)
async def on_scan_jobs_action(_: Any) -> None:
    await handle_scan_request()
@cl.action_callback(ACTION_SEARCH_SEEK)
async def on_search_seek_action(_: Any) -> None:
    await handle_seek_search_request()
@cl.action_callback(ACTION_SEARCH_DODA)
async def on_search_doda_action(_: Any) -> None:
    await handle_doda_search_request()
@cl.action_callback(ACTION_VIEW_PORTALS)
async def on_view_portals_action(_: Any) -> None:
    await handle_view_portals_request()
@cl.action_callback(ACTION_EDIT_PORTALS)
async def on_edit_portals_action(_: Any) -> None:
    await handle_start_portals_update()
@cl.action_callback(ACTION_VIEW_SCHEDULED_SCAN)
async def on_view_scheduled_scan_action(_: Any) -> None:
    await handle_view_scheduled_scan_settings()
@cl.action_callback(ACTION_EDIT_SCHEDULED_SCAN)
async def on_edit_scheduled_scan_action(_: Any) -> None:
    await handle_start_scheduled_scan_update()
@cl.action_callback(ACTION_TOGGLE_SCHEDULED_SCAN_FIELD)
async def on_toggle_scheduled_scan_field_action(action: Any) -> None:
    payload = getattr(action, "payload", {}) or {}
    field = payload.get("field")
    if not field:
        return
    await handle_toggle_scheduled_scan_field(field, payload.get("value"))
@cl.action_callback(ACTION_PROMPT_SCHEDULED_SCAN_FIELD)
async def on_prompt_scheduled_scan_field_action(action: Any) -> None:
    payload = getattr(action, "payload", {}) or {}
    field = payload.get("field")
    if not field:
        return
    await handle_prompt_scheduled_scan_field(field)
@cl.action_callback(ACTION_MARK_JOB_APPLIED)
async def on_mark_job_applied_action(action: Any) -> None:
    payload = getattr(action, "payload", {}) or {}
    job_key = payload.get("job_key")
    if not job_key:
        return
    await handle_mark_job_applied(job_key)
@cl.action_callback(ACTION_DELETE_CURRENT_THREAD)
async def on_delete_current_thread_action(_: Any) -> None:
    thread_id = getattr(context.session, "thread_id", None)
    if not thread_id:
        return
    await data_layer.delete_thread(thread_id)
    cl.user_session.set(SESSION_LAST_JOB_DESCRIPTION, None)
    cl.user_session.set(SESSION_LAST_TAILORED_RESUME_ID, None)
    cl.user_session.set(SESSION_THREAD_NAMED, False)
    cl.user_session.set(SESSION_PENDING_ACTION, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_EDIT_FIELD, None)
    cl.user_session.set(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE, False)
    await cl.Message(
        content="当前对话历史已经清空，后续消息会作为新的会话继续记录。",
        actions=build_tool_actions(),
    ).send()


@cl.on_settings_update
async def on_settings_update(settings: dict[str, Any]) -> None:
    if not cl.user_session.get(SESSION_SCHEDULED_SCAN_SETTINGS_FORM_ACTIVE):
        return
    await handle_scheduled_scan_settings_form_update(settings)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    uploaded_files = extract_supported_files(getattr(message, "elements", None))
    if uploaded_files:
        await process_resume_upload(uploaded_files[0])
        return

    resume_id = await get_resume_id_from_session()
    user_text = (message.content or "").strip()
    if not user_text:
        await cl.Message(
            content="You can paste a JD directly, or tell me what you want me to do next.",
        ).send()
        return
    if not cl.user_session.get(SESSION_THREAD_NAMED):
        await data_layer.update_thread(
            thread_id=context.session.thread_id,
            name=user_text,
            user_id=get_current_user_id(),
        )
        cl.user_session.set(SESSION_THREAD_NAMED, True)
        await sync_thread_metadata()
    try:
        pending_action = cl.user_session.get(SESSION_PENDING_ACTION)
        if pending_action == PENDING_UPDATE_PORTALS:
            await handle_portals_update_submission(user_text)
            return
        if pending_action == PENDING_UPDATE_SCHEDULED_SCAN:
            await handle_scheduled_scan_update_submission(user_text)
            return
        if pending_action == PENDING_EVALUATE_JOB:
            if not resume_id:
                await ensure_resume_available()
                return
            await handle_career_ops_evaluation(user_text, resume_id)
            return
        if pending_action == PENDING_DOWNLOAD_TAILORED_PDF:
            if not resume_id:
                await ensure_resume_available()
                return
            await handle_generate_tailored_pdf(user_text, resume_id)
            return
        if is_scan_request(user_text):
            await handle_scan_request()
            return
        if is_portals_edit_request(user_text):
            await handle_start_portals_update()
            return
        if is_portals_view_request(user_text):
            await handle_view_portals_request()
            return
        if is_scheduled_scan_view_request(user_text):
            await handle_view_scheduled_scan_settings()
            return
        if is_scheduled_scan_edit_request(user_text):
            await handle_start_scheduled_scan_update()
            return
        if not resume_id:
            await cl.Message(
                content="Upload a primary resume first, then I can keep helping with analysis and optimization.",
            ).send()
            return
        if is_career_ops_evaluate_request(user_text):
            await handle_career_ops_evaluation(user_text, resume_id)
            return
        if is_analysis_request(user_text):
            await handle_analysis_request(user_text, resume_id)
            return
        if is_optimize_request(user_text) or looks_like_job_description(user_text):
            await handle_optimization_request(user_text, resume_id)
            return
        await cl.Message(content=build_general_reply(user_text)).send()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text.strip() or exc.response.reason_phrase
        await cl.Message(
            content=(
                "The backend did not return a successful result this time.\n\n"
                f"- status: `{exc.response.status_code}`\n"
                f"- detail: `{detail[:300]}`\n\n"
                "Send the same JD again and I can keep debugging with you."
            )
        ).send()
    except Exception as exc:  # pragma: no cover - defensive branch
        await cl.Message(
            content=f"Something went wrong while handling this request: `{str(exc)[:300]}`",
        ).send()
