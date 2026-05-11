"""Pydantic models matching frontend expectations."""

import copy
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

_TEXT_VALUE_KEYS = (
    "text",
    "summary",
    "description",
    "value",
    "content",
    "title",
    "subtitle",
    "name",
    "label",
)
_BULLET_PREFIX_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")


def _extract_text_fragments(
    value: Any, depth: int = 0, max_depth: int = 10
) -> list[str]:
    """Extract text-like content from nested list/dict values."""
    if depth >= max_depth or value is None:
        return []

    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []

    if isinstance(value, (int, float)):
        return [str(value)]

    if isinstance(value, list):
        fragments: list[str] = []
        for item in value:
            fragments.extend(_extract_text_fragments(item, depth + 1, max_depth))
        return fragments

    if isinstance(value, dict):
        fragments: list[str] = []

        for key in _TEXT_VALUE_KEYS:
            if key in value:
                fragments.extend(
                    _extract_text_fragments(value.get(key), depth + 1, max_depth)
                )

        if fragments:
            return fragments

        for nested in value.values():
            fragments.extend(_extract_text_fragments(nested, depth + 1, max_depth))
        return fragments

    return []


def _coerce_text(value: Any, joiner: str = " ") -> str:
    """Coerce nested values into a single text string."""
    return joiner.join(_extract_text_fragments(value)).strip()


def _coerce_optional_text(value: Any) -> str | None:
    """Coerce nested values into optional text."""
    if value is None:
        return None
    text = _coerce_text(value)
    return text or None


def _split_description_lines(value: str) -> list[str]:
    """Split a description block into clean bullet lines."""
    items: list[str] = []
    for raw_line in re.split(r"\r?\n+", value):
        line = _BULLET_PREFIX_RE.sub("", raw_line.strip())
        if line:
            items.append(line)
    return items


def _coerce_string_list(value: Any) -> list[str]:
    """Coerce nested/string values into a list of strings."""
    if value is None:
        return []

    if isinstance(value, str):
        return _split_description_lines(value)

    if isinstance(value, list):
        items: list[str] = []
        for entry in value:
            if isinstance(entry, str):
                items.extend(_split_description_lines(entry))
                continue

            coerced = _coerce_text(entry)
            if coerced:
                items.append(coerced)
        return items

    coerced = _coerce_text(value)
    return [coerced] if coerced else []


# Section Type Enum for dynamic sections
class SectionType(str, Enum):
    """Types of resume sections."""

    PERSONAL_INFO = "personalInfo"  # Special: always first, not reorderable
    TEXT = "text"  # Single text block (like summary)
    ITEM_LIST = "itemList"  # Array of items with fields (like experience)
    STRING_LIST = "stringList"  # Array of strings (like skills)


# Resume Data Models (matching frontend types in resume-component.tsx)
class PersonalInfo(BaseModel):
    """Personal information section."""

    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str | None = None
    linkedin: str | None = None
    github: str | None = None


class Experience(BaseModel):
    """Work experience entry."""

    id: int = 0
    title: str = ""
    company: str = ""
    location: str | None = None
    years: str = ""
    description: list[str] = Field(default_factory=list)

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> list[str]:
        return _coerce_string_list(value)


class Education(BaseModel):
    """Education entry."""

    id: int = 0
    institution: str = ""
    degree: str = ""
    years: str = ""
    description: str | None = None

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> str | None:
        return _coerce_optional_text(value)


class Project(BaseModel):
    """Personal project entry."""

    id: int = 0
    name: str = ""
    role: str = ""
    years: str = ""
    github: str | None = None
    website: str | None = None
    description: list[str] = Field(default_factory=list)

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> list[str]:
        return _coerce_string_list(value)


class AdditionalInfo(BaseModel):
    """Additional information section."""

    technicalSkills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certificationsTraining: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)

    @field_validator(
        "technicalSkills",
        "languages",
        "certificationsTraining",
        "awards",
        mode="before",
    )
    @classmethod
    def _normalize_string_fields(cls, value: Any) -> list[str]:
        return _coerce_string_list(value)


# Section Metadata Models for dynamic section management
class SectionMeta(BaseModel):
    """Metadata for a resume section."""

    id: str  # Unique identifier (e.g., "summary", "custom_1")
    key: str  # Data key (matches ResumeData field or customSections key)
    displayName: str  # User-visible name
    sectionType: SectionType  # Type of section
    isDefault: bool = True  # True for built-in sections
    isVisible: bool = True  # Whether to show in resume
    order: int = 0  # Display order (0 = first after personalInfo)


class CustomSectionItem(BaseModel):
    """Generic item for custom item-based sections."""

    id: int = 0
    title: str = ""  # Primary title
    subtitle: str | None = None  # Secondary info (company, institution, etc.)
    location: str | None = None
    years: str = ""
    description: list[str] = Field(default_factory=list)

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> list[str]:
        return _coerce_string_list(value)


class CustomSection(BaseModel):
    """Custom section data container."""

    sectionType: SectionType
    items: list[CustomSectionItem] | None = None  # For ITEM_LIST
    strings: list[str] | None = None  # For STRING_LIST
    text: str | None = None  # For TEXT

    @field_validator("items", mode="before")
    @classmethod
    def _normalize_items(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, list):
            return value
        result = []
        for i, item in enumerate(value):
            if isinstance(item, str):
                result.append({"id": i + 1, "title": item})
            else:
                result.append(item)
        return result

    @field_validator("strings", mode="before")
    @classmethod
    def _normalize_strings(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        return _coerce_string_list(value)

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any) -> str | None:
        return _coerce_optional_text(value)


# Default section metadata for backward compatibility
DEFAULT_SECTION_META: list[dict[str, Any]] = [
    {
        "id": "personalInfo",
        "key": "personalInfo",
        "displayName": "Personal Info",
        "sectionType": SectionType.PERSONAL_INFO,
        "isDefault": True,
        "isVisible": True,
        "order": 0,
    },
    {
        "id": "summary",
        "key": "summary",
        "displayName": "Summary",
        "sectionType": SectionType.TEXT,
        "isDefault": True,
        "isVisible": True,
        "order": 1,
    },
    {
        "id": "workExperience",
        "key": "workExperience",
        "displayName": "Experience",
        "sectionType": SectionType.ITEM_LIST,
        "isDefault": True,
        "isVisible": True,
        "order": 2,
    },
    {
        "id": "education",
        "key": "education",
        "displayName": "Education",
        "sectionType": SectionType.ITEM_LIST,
        "isDefault": True,
        "isVisible": True,
        "order": 3,
    },
    {
        "id": "personalProjects",
        "key": "personalProjects",
        "displayName": "Projects",
        "sectionType": SectionType.ITEM_LIST,
        "isDefault": True,
        "isVisible": True,
        "order": 4,
    },
    {
        "id": "additional",
        "key": "additional",
        "displayName": "Skills & Awards",
        "sectionType": SectionType.STRING_LIST,
        "isDefault": True,
        "isVisible": True,
        "order": 5,
    },
]


def normalize_resume_data(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure resume data has section metadata (migration helper).

    This function is used for lazy migration of existing resumes
    that don't have sectionMeta or customSections fields.
    """
    if not data.get("sectionMeta"):
        # Use deepcopy to avoid shared mutable reference bug
        # Without this, all resumes would share the same list reference
        data["sectionMeta"] = copy.deepcopy(DEFAULT_SECTION_META)
    if "customSections" not in data:
        data["customSections"] = {}
    return data


class ResumeData(BaseModel):
    """Complete structured resume data."""

    # Existing fields (kept for backward compatibility)
    personalInfo: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: str = ""
    workExperience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    personalProjects: list[Project] = Field(default_factory=list)
    additional: AdditionalInfo = Field(default_factory=AdditionalInfo)

    # NEW: Section metadata and custom sections
    sectionMeta: list[SectionMeta] = Field(default_factory=list)
    customSections: dict[str, CustomSection] = Field(default_factory=dict)

    @field_validator("summary", mode="before")
    @classmethod
    def _normalize_summary(cls, value: Any) -> str:
        return _coerce_text(value)


# API Response Models
class ResumeUploadResponse(BaseModel):
    """Response for resume upload."""

    message: str
    request_id: str
    resume_id: str
    processing_status: Literal["pending", "processing", "ready", "failed"] = "pending"
    is_master: bool = False


class RawResume(BaseModel):
    """Raw resume data from database."""

    id: int | None = None
    content: str
    content_type: str = "md"
    created_at: str
    processing_status: str = "pending"  # pending, processing, ready, failed


class ResumeFetchData(BaseModel):
    """Data payload for resume fetch response."""

    resume_id: str
    raw_resume: RawResume
    processed_resume: ResumeData | None = None
    cover_letter: str | None = None
    outreach_message: str | None = None
    parent_id: str | None = None  # For determining if resume is tailored
    title: str | None = None


class ResumeFetchResponse(BaseModel):
    """Response for resume fetch."""

    request_id: str
    data: ResumeFetchData


class ResumeSummary(BaseModel):
    """Summary details for listing resumes."""

    resume_id: str
    filename: str | None = None
    is_master: bool = False
    parent_id: str | None = None
    processing_status: str = "pending"
    created_at: str
    updated_at: str
    title: str | None = None


class ResumeListResponse(BaseModel):
    """Response for resume list."""

    request_id: str
    data: list[ResumeSummary]


# Job Description Models
class JobUploadRequest(BaseModel):
    """Request to upload job descriptions."""

    job_descriptions: list[str]
    resume_id: str | None = None


class JobUploadResponse(BaseModel):
    """Response for job upload."""

    message: str
    job_id: list[str]
    request: dict[str, Any]


class CareerOpsScoreDimension(BaseModel):
    """Single structured score used by the Career Ops evaluator."""

    key: str
    category: Literal["A", "B", "C", "D", "E", "F"]
    label: str
    score: float = Field(ge=0.0, le=5.0)
    rationale: str
    evidence: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class CareerOpsEvaluationData(BaseModel):
    """Structured A-F job evaluation payload."""

    overall_score: float = Field(ge=0.0, le=5.0)
    overall_label: str
    executive_summary: str
    archetype: str
    af_scores: dict[str, float] = Field(default_factory=dict)
    dimensions: list[CareerOpsScoreDimension] = Field(default_factory=list)
    tailoring_priorities: list[str] = Field(default_factory=list)
    interview_focus: list[str] = Field(default_factory=list)
    keyword_targets: list[str] = Field(default_factory=list)
    market_data: "CareerOpsMarketData | None" = None


class CareerOpsEvaluateRequest(BaseModel):
    """Request payload for POST /api/evaluate-job."""

    resume: dict[str, Any] | str
    job_description: str


class CareerOpsEvaluateResponse(BaseModel):
    """Response payload for POST /api/evaluate-job."""

    request_id: str
    data: CareerOpsEvaluationData


class TranslateJobDescriptionRequest(BaseModel):
    """Request payload for POST /api/translate-job-description."""

    job_description: str


class TranslateJobDescriptionResponse(BaseModel):
    """Translated JD payload for frontend display."""

    request_id: str
    translated_job_description: str


class GenerateTailoredPDFRequest(BaseModel):
    """Request payload for POST /api/generate-tailored-pdf."""

    resume: dict[str, Any] | str
    job_description: str
    page_size: Literal["A4", "LETTER"] = "A4"


class TailoredPDFResult(BaseModel):
    """In-memory result returned by the Career Ops PDF generator."""

    filename: str
    pdf_bytes: bytes
    tailored_resume: ResumeData
    keyword_targets: list[str] = Field(default_factory=list)


class CareerOpsMarketSource(BaseModel):
    """Single live market-data source."""

    title: str
    url: str
    snippet: str = ""


class CareerOpsMarketData(BaseModel):
    """Live market signals used for Block D enrichment."""

    role_query: str
    company_name: str | None = None
    salary_mentions: list[str] = Field(default_factory=list)
    demand_summary: str = ""
    compensation_summary: str = ""
    sources: list[CareerOpsMarketSource] = Field(default_factory=list)


class CareerOpsScannedOffer(BaseModel):
    """Single job offer found by the portal scanner."""

    title: str
    url: str
    company: str
    location: str = ""
    source: str


class CareerOpsScanData(BaseModel):
    """Summary for a portal scan run."""

    scanned_companies: int = 0
    total_jobs_found: int = 0
    filtered_out: int = 0
    duplicates: int = 0
    new_offers: list[CareerOpsScannedOffer] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CareerOpsScanResponse(BaseModel):
    """Response payload for the scanner API."""

    request_id: str
    data: CareerOpsScanData


class SeekRawJob(BaseModel):
    """Raw first-page SEEK list result."""

    search_keyword: str
    title: str
    company: str
    location: str = ""
    salary: str | None = None
    work_type: str | None = None
    listed_at: str | None = None
    job_url: str = ""
    summary: str | None = None
    is_new: bool = False


class SeekSearchPlan(BaseModel):
    """Search plan generated from a resume."""

    resume_id: str
    source: str = "seek"
    candidate_profile_summary: str
    keywords: list[str] = Field(default_factory=list)
    location: str


class SeekSearchJob(BaseModel):
    """Normalized SEEK result used by frontend and notifications."""

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
    language: str | None = None
    raw_location_text: str | None = None
    raw_salary_text: str | None = None
    match_score: float = 0.0


class SeekSearchStats(BaseModel):
    """Summary stats for one SEEK search run."""

    keywords_generated: int = 0
    queries_attempted: int = 0
    queries_succeeded: int = 0
    raw_jobs_found: int = 0
    jobs_after_dedupe: int = 0


class SeekSearchError(BaseModel):
    """Per-keyword non-fatal search error."""

    search_keyword: str
    message: str


class SeekManualSearchRequest(BaseModel):
    """Manual SEEK search request payload."""

    resume_id: str
    location: str | None = None


class SeekManualSearchResponse(BaseModel):
    """Manual SEEK search response payload."""

    plan: SeekSearchPlan
    jobs: list[SeekSearchJob] = Field(default_factory=list)
    stats: SeekSearchStats
    errors: list[SeekSearchError] = Field(default_factory=list)


class MultilingualResumeAssets(BaseModel):
    """Current active resume ids by language."""

    candidate_id: str = "default"
    resume_en_id: str | None = None
    resume_ja_id: str | None = None
    resume_zh_id: str | None = None
    updated_at: str | None = None


class ScheduledScanConfig(BaseModel):
    """Stored daily scheduled scan configuration."""

    enabled: bool = False
    run_time_local: str = "09:00"
    timezone: str = "Australia/Sydney"
    seek_enabled: bool = False
    doda_enabled: bool = False
    boss_enabled: bool = False
    feishu_enabled: bool = False
    feishu_webhook_url: str | None = None
    high_score_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    last_run_at: str | None = None
    last_run_date_local: str | None = None
    last_run_status: str | None = None
    last_error: str | None = None
    last_result_counts: dict[str, Any] = Field(default_factory=dict)


class ScheduledScanConfigUpdateRequest(BaseModel):
    """Request payload for updating daily scheduled scan settings."""

    enabled: bool = False
    run_time_local: str = "09:00"
    timezone: str = "Australia/Sydney"
    seek_enabled: bool = False
    doda_enabled: bool = False
    boss_enabled: bool = False
    feishu_enabled: bool = False
    feishu_webhook_url: str | None = None
    high_score_threshold: float = Field(default=0.75, ge=0.0, le=1.0)


class DiscoveredJobRecord(BaseModel):
    """Persisted job discovered by scheduled scans."""

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
    status: Literal["new", "applied", "dismissed"] = "new"


class ScheduledScanSettingsResponse(BaseModel):
    """Frontend-ready scheduled scan settings payload."""

    config: ScheduledScanConfig
    assets: MultilingualResumeAssets
    recent_new_jobs: list[DiscoveredJobRecord] = Field(default_factory=list)
    high_score_unapplied_jobs: list[DiscoveredJobRecord] = Field(default_factory=list)


class DiscoveredJobStatusUpdateRequest(BaseModel):
    """Update payload for manually marking discovered job status."""

    job_key: str
    status: Literal["new", "applied", "dismissed"]


class PortalsTitleFilter(BaseModel):
    """Positive/negative title filter config."""

    positive: list[str] = Field(default_factory=list)
    negative: list[str] = Field(default_factory=list)
    seniority_boost: list[str] = Field(default_factory=list)


class PortalsSearchQuery(BaseModel):
    """Saved web-search query definition."""

    name: str
    query: str
    enabled: bool = True


class PortalsTrackedCompany(BaseModel):
    """Tracked company career-page configuration."""

    name: str
    careers_url: str
    enabled: bool = True
    api: str | None = None
    scan_method: str | None = None
    scan_query: str | None = None
    notes: str | None = None


class PortalsConfig(BaseModel):
    """Structured portals.yml content."""

    title_filter: PortalsTitleFilter = Field(default_factory=PortalsTitleFilter)
    search_queries: list[PortalsSearchQuery] = Field(default_factory=list)
    tracked_companies: list[PortalsTrackedCompany] = Field(default_factory=list)


# Improvement Models
class ImproveResumeRequest(BaseModel):
    """Request to improve/tailor a resume."""

    resume_id: str
    job_id: str
    prompt_id: str | None = None


class ImprovementSuggestion(BaseModel):
    """Single improvement suggestion."""

    suggestion: str
    lineNumber: int | None = None


class ResumeFieldDiff(BaseModel):
    """Single field change record."""

    field_path: str  # Example: "workExperience[0].description[2]"
    field_type: Literal[
        "skill",
        "description",
        "summary",
        "certification",
        "experience",
        "education",
        "project",
    ]
    change_type: Literal["added", "removed", "modified"]
    original_value: str | None = None
    new_value: str | None = None
    confidence: Literal["low", "medium", "high"] = "medium"


class ResumeDiffSummary(BaseModel):
    """Change summary stats."""

    total_changes: int
    skills_added: int
    skills_removed: int
    descriptions_modified: int
    certifications_added: int
    high_risk_changes: int  # High-risk additions


class RefinementStats(BaseModel):
    """Statistics from the multi-pass refinement process."""

    passes_completed: int = Field(default=0, ge=0, description="Number of passes run")
    keywords_injected: int = Field(
        default=0, ge=0, description="Number of keywords injected"
    )
    ai_phrases_removed: list[str] = Field(
        default_factory=list, description="List of AI phrases that were removed"
    )
    alignment_violations_fixed: int = Field(
        default=0, ge=0, description="Number of alignment violations corrected"
    )
    initial_match_percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Keyword match before refinement",
    )
    final_match_percentage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Keyword match after refinement"
    )


class ImproveResumeData(BaseModel):
    """Data payload for improve response."""

    request_id: str
    resume_id: str | None = Field(
        default=None,
        description="Null for preview responses; populated when the tailored resume is persisted.",
    )
    job_id: str
    resume_preview: ResumeData
    improvements: list[ImprovementSuggestion]
    markdownOriginal: str | None = None
    markdownImproved: str | None = None
    cover_letter: str | None = None
    outreach_message: str | None = None

    # Diff metadata
    diff_summary: ResumeDiffSummary | None = None
    detailed_changes: list[ResumeFieldDiff] | None = None

    # Refinement metadata (multi-pass refinement stats)
    refinement_stats: "RefinementStats | None" = None

    # Warning and status fields for transparency
    warnings: list[str] = Field(default_factory=list)
    refinement_attempted: bool = False
    refinement_successful: bool = False


class ImproveResumeResponse(BaseModel):
    """Response for resume improvement."""

    request_id: str
    data: ImproveResumeData


class ImproveResumeConfirmRequest(BaseModel):
    """Request to confirm and save a tailored resume."""

    resume_id: str
    job_id: str
    improved_data: ResumeData
    improvements: list[ImprovementSuggestion]


# Config Models
class LLMConfigRequest(BaseModel):
    """Request to update LLM configuration."""

    provider: str | None = None
    model: str | None = None
    api_key: str | None = None
    api_base: str | None = None


class LLMConfigResponse(BaseModel):
    """Response for LLM configuration."""

    provider: str
    model: str
    api_key: str  # Masked
    api_base: str | None = None


class FeatureConfigRequest(BaseModel):
    """Request to update feature settings."""

    enable_cover_letter: bool | None = None
    enable_outreach_message: bool | None = None


class FeatureConfigResponse(BaseModel):
    """Response for feature settings."""

    enable_cover_letter: bool = False
    enable_outreach_message: bool = False


class LanguageConfigRequest(BaseModel):
    """Request to update language settings."""

    ui_language: str | None = None  # en, es, zh, ja - for interface
    content_language: str | None = None  # en, es, zh, ja - for generated content


class LanguageConfigResponse(BaseModel):
    """Response for language settings."""

    ui_language: str = "en"  # Interface language
    content_language: str = "en"  # Generated content language
    supported_languages: list[str] = ["en", "es", "zh", "ja"]


class PromptOption(BaseModel):
    """Prompt option for resume tailoring."""

    id: str
    label: str
    description: str


class PromptConfigRequest(BaseModel):
    """Request to update prompt settings."""

    default_prompt_id: str | None = None


class PromptConfigResponse(BaseModel):
    """Response for prompt settings."""

    default_prompt_id: str
    prompt_options: list[PromptOption]


# API Key Management Models
class ApiKeyProviderStatus(BaseModel):
    """Status of a single API key provider."""

    provider: str  # openai, anthropic, google, etc.
    configured: bool
    masked_key: str | None = None  # Shows last 4 chars if configured


class ApiKeyStatusResponse(BaseModel):
    """Response for API key status check."""

    providers: list[ApiKeyProviderStatus]


class ApiKeysUpdateRequest(BaseModel):
    """Request to update API keys."""

    openai: str | None = None
    anthropic: str | None = None
    google: str | None = None
    openrouter: str | None = None
    deepseek: str | None = None


class ApiKeysUpdateResponse(BaseModel):
    """Response after updating API keys."""

    message: str
    updated_providers: list[str]


# Update Cover Letter/Outreach Models
class UpdateCoverLetterRequest(BaseModel):
    """Request to update cover letter content."""

    content: str


class UpdateOutreachMessageRequest(BaseModel):
    """Request to update outreach message content."""

    content: str


class UpdateTitleRequest(BaseModel):
    """Request to update resume title."""

    title: str


class ResetDatabaseRequest(BaseModel):
    """Request to reset database with confirmation."""

    confirm: str | None = None


class GenerateContentResponse(BaseModel):
    """Response for on-demand content generation."""

    content: str
    message: str


# Health/Status Models
class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    llm: dict[str, Any]


class StatusResponse(BaseModel):
    """Application status response."""

    status: str
    llm_configured: bool
    llm_healthy: bool
    has_master_resume: bool
    database_stats: dict[str, Any]


# Diff-Based Improvement Models


class ResumeChange(BaseModel):
    """A single targeted change the LLM wants to make to the resume."""

    path: str = Field(
        description="Dot+bracket path, e.g. 'workExperience[0].description[1]'"
    )
    action: Literal["replace", "append", "reorder"]
    original: str | None = Field(
        default=None, description="Current text at path — for verification"
    )
    value: str | list[str] = Field(description="New content")
    reason: str = Field(description="Why this change helps match the JD")


class ImproveDiffResult(BaseModel):
    """LLM output: a list of targeted resume changes."""

    changes: list[ResumeChange] = Field(default_factory=list)
    strategy_notes: str = Field(default="")
