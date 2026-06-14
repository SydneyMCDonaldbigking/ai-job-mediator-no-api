"""Deterministic JD profiling and resume evidence mapping for tailoring."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from app.career_ops.evaluator import coerce_resume_data
from app.schemas.models import ResumeData

JOB_TYPE_AI_ML = "ai_ml"
JOB_TYPE_SOFTWARE = "software_engineering"
JOB_TYPE_UX_PRODUCT = "ux_product"
JOB_TYPE_DATA_ANALYTICS = "data_analytics"
JOB_TYPE_OPERATIONS_CUSTOMER = "operations_customer"
JOB_TYPE_MARKETING_CONTENT = "marketing_content"
JOB_TYPE_GENERAL = "general"

TAG_AI_ML = "ai_ml"
TAG_SOFTWARE = "software"
TAG_DATA = "data"
TAG_DESIGN = "design"
TAG_CUSTOMER = "customer"
TAG_COLLABORATION = "collaboration"
TAG_OPERATIONS = "operations"
TAG_TECHNICAL = "technical"
TAG_LEADERSHIP = "leadership"
TAG_LOW_RELEVANCE = "low_relevance"

_JOB_TYPE_TERMS: dict[str, tuple[str, ...]] = {
    JOB_TYPE_AI_ML: (
        "ai engineer",
        "machine learning",
        "ml",
        "llm",
        "large language model",
        "generative ai",
        "genai",
        "rag",
        "retrieval",
        "model evaluation",
        "agent",
        "computer vision",
        "nlp",
        "prompt engineering",
    ),
    JOB_TYPE_SOFTWARE: (
        "software engineer",
        "software developer",
        "backend",
        "frontend",
        "full-stack",
        "full stack",
        "api",
        "fastapi",
        "react",
        "javascript",
        "typescript",
        "git",
        "testing",
        "deployment",
    ),
    JOB_TYPE_UX_PRODUCT: (
        "ux",
        "ui",
        "product designer",
        "product manager",
        "user-centred",
        "user-centered",
        "prototype",
        "prototyping",
        "figma",
        "usability",
        "workflow mapping",
        "stakeholder workshop",
    ),
    JOB_TYPE_DATA_ANALYTICS: (
        "data analyst",
        "data analytics",
        "analytics",
        "sql",
        "dashboard",
        "tableau",
        "power bi",
        "experiment",
        "insight",
        "statistics",
        "pandas",
        "data visualization",
    ),
    JOB_TYPE_OPERATIONS_CUSTOMER: (
        "operations",
        "customer service",
        "customer support",
        "customer success",
        "service workflow",
        "rostering",
        "process improvement",
        "customer feedback",
        "team coordination",
        "enquiries",
    ),
    JOB_TYPE_MARKETING_CONTENT: (
        "marketing",
        "social media",
        "content",
        "brand",
        "campaign",
        "audience",
        "community",
        "copywriting",
    ),
}
_JOB_TYPE_PRIORITY = {
    JOB_TYPE_AI_ML: 6,
    JOB_TYPE_SOFTWARE: 5,
    JOB_TYPE_UX_PRODUCT: 4,
    JOB_TYPE_DATA_ANALYTICS: 3,
    JOB_TYPE_OPERATIONS_CUSTOMER: 2,
    JOB_TYPE_MARKETING_CONTENT: 1,
}

_TAG_TERMS: dict[str, tuple[str, ...]] = {
    TAG_AI_ML: _JOB_TYPE_TERMS[JOB_TYPE_AI_ML]
    + (
        "prediction model",
        "classification",
        "vector retrieval",
        "automation",
    ),
    TAG_SOFTWARE: _JOB_TYPE_TERMS[JOB_TYPE_SOFTWARE]
    + (
        "python",
        "java",
        "node",
        "rest",
        "unit test",
        "debug",
        "code",
    ),
    TAG_DATA: _JOB_TYPE_TERMS[JOB_TYPE_DATA_ANALYTICS]
    + (
        "data pipeline",
        "data analysis",
        "eda",
        "metric",
        "model output",
        "opc data",
    ),
    TAG_DESIGN: _JOB_TYPE_TERMS[JOB_TYPE_UX_PRODUCT]
    + (
        "designed",
        "user flow",
        "interaction logic",
        "interface",
        "original products",
        "product planning",
    ),
    TAG_CUSTOMER: _JOB_TYPE_TERMS[JOB_TYPE_OPERATIONS_CUSTOMER]
    + (
        "consumer",
        "retail",
        "support",
        "service",
        "customer insight",
        "customer insights",
    ),
    TAG_COLLABORATION: (
        "collaborated",
        "team",
        "teammates",
        "stakeholder",
        "cross-functional",
        "partnered",
        "worked with",
        "communicated",
        "trained",
        "mentored",
    ),
    TAG_OPERATIONS: (
        "workflow",
        "operations",
        "process",
        "coordination",
        "delivery",
        "rostering",
        "deployment",
        "monitoring",
    ),
    TAG_LEADERSHIP: (
        "led",
        "managed",
        "owned",
        "founded",
        "operated",
        "coordinated",
    ),
}

_TECHNICAL_TAGS = {TAG_AI_ML, TAG_SOFTWARE, TAG_DATA}
_PROFILE_TAGS: dict[str, set[str]] = {
    JOB_TYPE_AI_ML: {TAG_AI_ML, TAG_SOFTWARE, TAG_DATA, TAG_TECHNICAL},
    JOB_TYPE_SOFTWARE: {TAG_SOFTWARE, TAG_DATA, TAG_TECHNICAL},
    JOB_TYPE_UX_PRODUCT: {TAG_DESIGN, TAG_CUSTOMER, TAG_COLLABORATION},
    JOB_TYPE_DATA_ANALYTICS: {TAG_DATA, TAG_SOFTWARE, TAG_TECHNICAL},
    JOB_TYPE_OPERATIONS_CUSTOMER: {TAG_CUSTOMER, TAG_OPERATIONS, TAG_COLLABORATION},
    JOB_TYPE_MARKETING_CONTENT: {TAG_CUSTOMER, TAG_DESIGN, TAG_COLLABORATION},
    JOB_TYPE_GENERAL: {TAG_COLLABORATION, TAG_CUSTOMER, TAG_OPERATIONS},
}
_TRANSFERABLE_TAGS = {TAG_COLLABORATION, TAG_OPERATIONS}


@dataclass(frozen=True)
class JobProfile:
    primary_type: str
    secondary_types: tuple[str, ...]
    scores: dict[str, int]
    keyword_targets: tuple[str, ...]


@dataclass(frozen=True)
class ResumeEvidenceEntry:
    section: str
    index: int
    title: str
    organization: str
    tags: tuple[str, ...]
    matched_keywords: tuple[str, ...]
    relevance_score: int
    is_low_relevance: bool


@dataclass(frozen=True)
class ResumeEvidenceMap:
    job_profile: JobProfile
    entries: tuple[ResumeEvidenceEntry, ...]

    def find(self, section: str, index: int) -> ResumeEvidenceEntry:
        for entry in self.entries:
            if entry.section == section and entry.index == index:
                return entry
        raise KeyError(f"No evidence entry for {section}[{index}]")


def _compact_whitespace(value: object) -> str:
    return " ".join(str(value or "").split()).strip()


def _contains_term(text: str, term: str) -> bool:
    lowered = _compact_whitespace(text).casefold()
    normalized_term = _compact_whitespace(term).casefold()
    if not normalized_term:
        return False
    if re.fullmatch(r"[a-z0-9+#./-]+", normalized_term):
        return bool(re.search(rf"(?<![a-z0-9+#./-]){re.escape(normalized_term)}(?![a-z0-9+#./-])", lowered))
    return normalized_term in lowered


def _score_terms(text: str, terms: Iterable[str]) -> int:
    return sum(1 for term in terms if _contains_term(text, term))


def infer_job_profile(
    job_description: str = "",
    keyword_targets: list[str] | tuple[str, ...] | None = None,
) -> JobProfile:
    """Infer a coarse JD type for downstream resume tailoring decisions."""
    keywords = tuple(_compact_whitespace(keyword) for keyword in (keyword_targets or []) if _compact_whitespace(keyword))
    text = _compact_whitespace(f"{job_description} {' '.join(keywords)}")
    scores = {
        job_type: _score_terms(text, terms)
        for job_type, terms in _JOB_TYPE_TERMS.items()
    }
    primary_type, primary_score = max(
        scores.items(),
        key=lambda item: (item[1], _JOB_TYPE_PRIORITY.get(item[0], 0)),
    )
    if primary_score == 0:
        primary_type = JOB_TYPE_GENERAL
    secondary_types = tuple(
        job_type
        for job_type, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))
        if job_type != primary_type and score > 0
    )
    return JobProfile(
        primary_type=primary_type,
        secondary_types=secondary_types,
        scores=scores,
        keyword_targets=keywords,
    )


def _matched_keywords(text: str, keyword_targets: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    matches: list[str] = []
    for keyword in keyword_targets:
        normalized = _compact_whitespace(keyword)
        if normalized and _contains_term(text, normalized):
            matches.append(normalized)
    return tuple(dict.fromkeys(matches))


def classify_resume_entry(
    *,
    section: str,
    index: int,
    title: str,
    organization: str,
    descriptions: list[str] | tuple[str, ...],
    keyword_targets: list[str] | tuple[str, ...],
    job_profile: JobProfile | None = None,
) -> ResumeEvidenceEntry:
    """Tag a resume entry and score how useful it is for the current JD."""
    job_profile = job_profile or infer_job_profile(keyword_targets=keyword_targets)
    text = _compact_whitespace(f"{title} {organization} {' '.join(descriptions)}")
    tags = {
        tag
        for tag, terms in _TAG_TERMS.items()
        if _score_terms(text, terms)
    }
    if tags & _TECHNICAL_TAGS:
        tags.add(TAG_TECHNICAL)

    matched = _matched_keywords(text, keyword_targets)
    profile_tags = _PROFILE_TAGS.get(job_profile.primary_type, _PROFILE_TAGS[JOB_TYPE_GENERAL])
    profile_hits = len(tags & profile_tags)
    transferable_hits = len(tags & _TRANSFERABLE_TAGS)
    relevance_score = len(matched) * 4 + profile_hits * 2 + transferable_hits
    is_single_bullet = len([item for item in descriptions if _compact_whitespace(item)]) <= 1
    is_low_relevance = is_single_bullet and not matched and profile_hits == 0 and transferable_hits == 0
    if is_low_relevance:
        tags.add(TAG_LOW_RELEVANCE)

    return ResumeEvidenceEntry(
        section=section,
        index=index,
        title=_compact_whitespace(title),
        organization=_compact_whitespace(organization),
        tags=tuple(sorted(tags)),
        matched_keywords=matched,
        relevance_score=relevance_score,
        is_low_relevance=is_low_relevance,
    )


def build_resume_evidence_map(
    resume: ResumeData | dict | str,
    *,
    keyword_targets: list[str] | tuple[str, ...],
    job_profile: JobProfile | None = None,
) -> ResumeEvidenceMap:
    """Build per-entry evidence tags for work experience and projects."""
    normalized_resume = coerce_resume_data(resume)
    job_profile = job_profile or infer_job_profile(keyword_targets=keyword_targets)
    entries: list[ResumeEvidenceEntry] = []

    for index, item in enumerate(normalized_resume.workExperience):
        entries.append(
            classify_resume_entry(
                section="workExperience",
                index=index,
                title=item.title,
                organization=item.company,
                descriptions=item.description,
                keyword_targets=keyword_targets,
                job_profile=job_profile,
            )
        )

    for index, item in enumerate(normalized_resume.personalProjects):
        entries.append(
            classify_resume_entry(
                section="personalProjects",
                index=index,
                title=item.role,
                organization=item.name,
                descriptions=item.description,
                keyword_targets=keyword_targets,
                job_profile=job_profile,
            )
        )

    return ResumeEvidenceMap(job_profile=job_profile, entries=tuple(entries))
