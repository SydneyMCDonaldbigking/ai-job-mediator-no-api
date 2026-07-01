from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResumeUploadResponse(BaseModel):
    message: str
    request_id: str
    resume_id: str
    processing_status: str = "pending"
    is_master: bool = False


class ResumeSummary(BaseModel):
    resume_id: str
    filename: str | None = None
    is_master: bool = False
    parent_id: str | None = None
    processing_status: str = "pending"
    created_at: str = ""
    updated_at: str = ""
    title: str | None = None


class ResumeListResponse(BaseModel):
    request_id: str | None = None
    data: list[ResumeSummary] = Field(default_factory=list)


class RawResume(BaseModel):
    content: str | None = None
    processing_status: str = "pending"


class ResumeFetchData(BaseModel):
    raw_resume: RawResume
    cover_letter: str | None = None
    outreach_message: str | None = None


class ResumeFetchResponse(BaseModel):
    data: ResumeFetchData


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


class TranslateJobDescriptionResponse(BaseModel):
    request_id: str
    translated_job_description: str


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


_MODELS_TO_REBUILD = (
    ResumeFetchData,
    ResumeFetchResponse,
    ResumeSummary,
    ResumeListResponse,
    ImproveResumeData,
    ImproveResumeResponse,
    CareerOpsEvaluationData,
    CareerOpsEvaluateResponse,
    TranslateJobDescriptionResponse,
    CareerOpsScanData,
    CareerOpsScanResponse,
    SeekSearchPlan,
    SeekSearchJob,
    SeekSearchStats,
    SeekSearchError,
    SeekSearchResponse,
    PortalsConfig,
    MultilingualResumeAssets,
    ScheduledScanConfig,
    DiscoveredJobRecord,
    ScheduledScanSettingsResponse,
)

for model in _MODELS_TO_REBUILD:
    model.model_rebuild()
