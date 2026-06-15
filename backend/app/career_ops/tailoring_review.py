"""Structured review reports for JD-tailored resumes.

The report explains what the tailoring pipeline did without asking the LLM for
another opinion. Keyword evidence is traced back to the source resume so the
product can distinguish genuine support from unsupported JD terms.
"""

from __future__ import annotations

from app.career_ops.evaluator import coerce_resume_data
from app.career_ops.resume_text import (
    _compact_whitespace,
    _contains_term,
    _dedupe_preserve_order,
)
from app.career_ops.tailoring_intelligence import (
    TAG_LOW_RELEVANCE,
    build_resume_evidence_map,
    infer_job_profile,
)
from app.career_ops.resume_tailoring import _tailor_resume
from app.schemas.models import (
    ResumeData,
    TailoringContentChange,
    TailoringEntryReview,
    TailoringKeywordEvidence,
    TailoringPreservationSummary,
    TailoringReviewJobProfile,
    TailoringReviewReport,
    TailoringReviewResult,
    TailoringReviewScores,
)

_REPORT_KEYWORD_NOISE = {
    "junior",
    "mid",
    "mid-level",
    "mid level",
    "senior",
    "lead",
    "principal",
    "intern",
    "internship",
    "graduate",
    "sydney",
    "nsw",
    "melbourne",
    "brisbane",
    "perth",
    "adelaide",
    "australia",
    "remote",
    "hybrid",
    "onsite",
    "on-site",
    "requiring",
    "requires",
    "required",
    "requirement",
    "requirements",
    "exposure",
    "experience",
    "role",
    "job",
    "candidate",
    "join",
    "hiring",
}


def _text_matches_keyword(text: object, keyword: str) -> bool:
    return _contains_term(_compact_whitespace(text), keyword)


def _clean_report_keywords(keyword_targets: list[str]) -> list[str]:
    clean_keywords: list[str] = []
    for keyword in _dedupe_preserve_order(keyword_targets):
        normalized = _compact_whitespace(keyword)
        if not normalized:
            continue
        if normalized.casefold() in _REPORT_KEYWORD_NOISE:
            continue
        clean_keywords.append(normalized)
    return clean_keywords


def _keyword_evidence_paths(resume: ResumeData, keyword: str) -> list[str]:
    paths: list[str] = []
    if _text_matches_keyword(resume.summary, keyword):
        paths.append("summary")

    for index, skill in enumerate(resume.additional.technicalSkills):
        if _text_matches_keyword(skill, keyword):
            paths.append(f"additional.technicalSkills[{index}]")

    for index, item in enumerate(resume.workExperience):
        if _text_matches_keyword(item.title, keyword):
            paths.append(f"workExperience[{index}].title")
        if _text_matches_keyword(item.company, keyword):
            paths.append(f"workExperience[{index}].company")
        for bullet_index, bullet in enumerate(item.description):
            if _text_matches_keyword(bullet, keyword):
                paths.append(f"workExperience[{index}].description[{bullet_index}]")

    for index, item in enumerate(resume.personalProjects):
        if _text_matches_keyword(item.name, keyword):
            paths.append(f"personalProjects[{index}].name")
        if _text_matches_keyword(item.role, keyword):
            paths.append(f"personalProjects[{index}].role")
        for bullet_index, bullet in enumerate(item.description):
            if _text_matches_keyword(bullet, keyword):
                paths.append(f"personalProjects[{index}].description[{bullet_index}]")

    return paths


def _keyword_evidence_summary(paths: list[str]) -> str:
    if not paths:
        return "No source-resume evidence found for this JD keyword."
    first_path = paths[0]
    if first_path.startswith("workExperience"):
        return "Supported by work experience evidence."
    if first_path.startswith("personalProjects"):
        return "Supported by project evidence."
    if first_path.startswith("additional.technicalSkills"):
        return "Supported by the candidate's skills list."
    return "Supported by the source resume."


def _build_keyword_evidence(
    original_resume: ResumeData,
    keyword_targets: list[str],
) -> list[TailoringKeywordEvidence]:
    evidence: list[TailoringKeywordEvidence] = []
    for keyword in _dedupe_preserve_order(keyword_targets):
        paths = _keyword_evidence_paths(original_resume, keyword)
        evidence.append(
            TailoringKeywordEvidence(
                keyword=keyword,
                supported=bool(paths),
                evidence_paths=paths,
                evidence_summary=_keyword_evidence_summary(paths),
            )
        )
    return evidence


def _entry_decision(is_low_relevance: bool, relevance_score: int, matched_keywords: list[str]) -> str:
    if is_low_relevance:
        return "kept_lower_priority"
    if relevance_score >= 8:
        return "prioritized"
    if matched_keywords:
        return "jd_aligned"
    return "kept_context"


def _entry_rationale(decision: str, matched_keywords: list[str], evidence_tags: list[str]) -> str:
    if decision == "kept_lower_priority":
        return "Kept for completeness, but placed as lower-priority evidence because it has limited JD overlap."
    if matched_keywords:
        return f"Aligned to JD evidence through: {', '.join(matched_keywords[:5])}."
    if evidence_tags:
        return f"Kept as transferable context with evidence tags: {', '.join(evidence_tags[:5])}."
    return "Kept as source-resume context without inventing a stronger claim."


def _build_entry_reviews(
    tailored_resume: ResumeData,
    job_description: str,
    keyword_targets: list[str],
) -> list[TailoringEntryReview]:
    job_profile = infer_job_profile(job_description, keyword_targets=keyword_targets)
    evidence_map = build_resume_evidence_map(
        tailored_resume,
        keyword_targets=keyword_targets,
        job_profile=job_profile,
    )
    reviews: list[TailoringEntryReview] = []
    for entry in evidence_map.entries:
        evidence_tags = list(entry.tags)
        matched_keywords = list(entry.matched_keywords)
        decision = _entry_decision(
            entry.is_low_relevance,
            entry.relevance_score,
            matched_keywords,
        )
        reviews.append(
            TailoringEntryReview(
                section=entry.section,
                index=entry.index,
                title=entry.title,
                organization=entry.organization,
                evidence_tags=evidence_tags,
                matched_keywords=matched_keywords,
                relevance_score=entry.relevance_score,
                decision=decision,
                rationale=_entry_rationale(decision, matched_keywords, evidence_tags),
            )
        )
    return reviews


def _count_removed(original_count: int, tailored_count: int) -> int:
    return max(0, original_count - tailored_count)


def _build_preservation_summary(
    original_resume: ResumeData,
    tailored_resume: ResumeData,
) -> TailoringPreservationSummary:
    original_skills = [
        _compact_whitespace(skill)
        for skill in original_resume.additional.technicalSkills
        if _compact_whitespace(skill)
    ]
    tailored_skills = [
        _compact_whitespace(skill)
        for skill in tailored_resume.additional.technicalSkills
        if _compact_whitespace(skill)
    ]
    return TailoringPreservationSummary(
        work_experience_original_count=len(original_resume.workExperience),
        work_experience_tailored_count=len(tailored_resume.workExperience),
        removed_work_experience_count=_count_removed(
            len(original_resume.workExperience),
            len(tailored_resume.workExperience),
        ),
        project_original_count=len(original_resume.personalProjects),
        project_tailored_count=len(tailored_resume.personalProjects),
        removed_project_count=_count_removed(
            len(original_resume.personalProjects),
            len(tailored_resume.personalProjects),
        ),
        skill_original_count=len(original_skills),
        skill_tailored_count=len(tailored_skills),
        removed_skill_count=_count_removed(len(original_skills), len(tailored_skills)),
    )


def _build_content_changes(
    original_resume: ResumeData,
    tailored_resume: ResumeData,
) -> list[TailoringContentChange]:
    changes: list[TailoringContentChange] = []
    if _compact_whitespace(original_resume.summary) != _compact_whitespace(tailored_resume.summary):
        changes.append(
            TailoringContentChange(
                path="summary",
                change_type="rephrased",
                before=_compact_whitespace(original_resume.summary),
                after=_compact_whitespace(tailored_resume.summary),
                reason="Summary was adjusted to foreground JD-aligned evidence while preserving source facts.",
            )
        )

    original_skills = [
        _compact_whitespace(skill)
        for skill in original_resume.additional.technicalSkills
        if _compact_whitespace(skill)
    ]
    tailored_skills = [
        _compact_whitespace(skill)
        for skill in tailored_resume.additional.technicalSkills
        if _compact_whitespace(skill)
    ]
    if original_skills and tailored_skills and original_skills != tailored_skills:
        changes.append(
            TailoringContentChange(
                path="additional.technicalSkills",
                change_type="reordered",
                before=", ".join(original_skills),
                after=", ".join(tailored_skills),
                reason="Skills were reordered by JD relevance without treating unsupported keywords as evidence.",
            )
        )

    for index, original_item in enumerate(original_resume.workExperience):
        if index >= len(tailored_resume.workExperience):
            continue
        tailored_item = tailored_resume.workExperience[index]
        for bullet_index, original_bullet in enumerate(original_item.description):
            if bullet_index >= len(tailored_item.description):
                continue
            tailored_bullet = tailored_item.description[bullet_index]
            if _compact_whitespace(original_bullet) != _compact_whitespace(tailored_bullet):
                changes.append(
                    TailoringContentChange(
                        path=f"workExperience[{index}].description[{bullet_index}]",
                        change_type="rephrased",
                        before=_compact_whitespace(original_bullet),
                        after=_compact_whitespace(tailored_bullet),
                        reason="Bullet wording changed to improve professional tone or JD alignment.",
                    )
                )
    return changes


def _score_report(
    keyword_evidence: list[TailoringKeywordEvidence],
    entry_reviews: list[TailoringEntryReview],
    preservation_summary: TailoringPreservationSummary,
) -> TailoringReviewScores:
    supported_count = sum(1 for item in keyword_evidence if item.supported)
    keyword_count = max(1, len(keyword_evidence))
    support_ratio = supported_count / keyword_count
    top_relevance = max((entry.relevance_score for entry in entry_reviews), default=0)
    low_relevance_count = sum(1 for entry in entry_reviews if entry.decision == "kept_lower_priority")
    deletion_penalty = (
        preservation_summary.removed_work_experience_count
        + preservation_summary.removed_project_count
        + preservation_summary.removed_skill_count
    ) * 8

    ats_score = max(0, min(100, round(35 + support_ratio * 60 - deletion_penalty)))
    hr_score = max(0, min(100, round(45 + support_ratio * 35 + min(top_relevance, 10) * 2 - low_relevance_count * 3)))
    hiring_manager_score = max(
        0,
        min(100, round(40 + support_ratio * 30 + min(top_relevance, 12) * 3 - deletion_penalty)),
    )

    notes = [
        f"{supported_count} of {len(keyword_evidence)} JD keywords have source-resume evidence.",
        "Low-relevance entries are flagged for review instead of being silently deleted.",
    ]
    if deletion_penalty:
        notes.append("One or more source sections appear reduced and should be reviewed before export.")
    return TailoringReviewScores(
        ats_score=ats_score,
        hr_score=hr_score,
        hiring_manager_score=hiring_manager_score,
        notes=notes,
    )


def _top_alignment_reasons(
    keyword_evidence: list[TailoringKeywordEvidence],
    entry_reviews: list[TailoringEntryReview],
) -> list[str]:
    supported = [item.keyword for item in keyword_evidence if item.supported]
    unsupported = [item.keyword for item in keyword_evidence if not item.supported]
    reasons: list[str] = []
    if supported:
        reasons.append(f"Matched source-resume evidence for: {', '.join(supported[:6])}.")
    else:
        reasons.append("No JD keyword target has direct source-resume evidence.")
    top_entries = [
        entry for entry in sorted(entry_reviews, key=lambda item: -item.relevance_score)
        if entry.relevance_score > 0
    ]
    if top_entries:
        top = top_entries[0]
        reasons.append(f"Strongest evidence entry: {top.title} at {top.organization}.")
    if unsupported:
        reasons.append(f"Unsupported JD terms left unclaimed: {', '.join(unsupported[:6])}.")
    return reasons


def build_tailoring_review_report(
    *,
    original_resume: ResumeData | dict | str,
    tailored_resume: ResumeData | dict | str,
    job_description: str,
    keyword_targets: list[str],
) -> TailoringReviewReport:
    """Build a deterministic explanation for a tailored resume/PDF result."""
    normalized_original = coerce_resume_data(original_resume)
    normalized_tailored = coerce_resume_data(tailored_resume)
    clean_keywords = _clean_report_keywords(keyword_targets)
    job_profile = infer_job_profile(job_description, keyword_targets=clean_keywords)
    keyword_evidence = _build_keyword_evidence(normalized_original, clean_keywords)
    unsupported_keywords = [item.keyword for item in keyword_evidence if not item.supported]
    entry_reviews = _build_entry_reviews(
        normalized_tailored,
        job_description,
        clean_keywords,
    )
    preservation_summary = _build_preservation_summary(normalized_original, normalized_tailored)
    scores = _score_report(keyword_evidence, entry_reviews, preservation_summary)

    safety_notes = [
        "Keyword evidence is traced to the original uploaded resume, not to generated wording alone.",
        "Unsupported JD terms are reported instead of being presented as candidate experience.",
    ]
    if unsupported_keywords:
        safety_notes.append(
            f"Unsupported keywords requiring human review: {', '.join(unsupported_keywords[:8])}."
        )

    return TailoringReviewReport(
        job_profile=TailoringReviewJobProfile(
            primary_type=job_profile.primary_type,
            secondary_types=list(job_profile.secondary_types),
            keyword_targets=list(job_profile.keyword_targets),
        ),
        keyword_evidence=keyword_evidence,
        unsupported_keywords=unsupported_keywords,
        entry_reviews=entry_reviews,
        content_changes=_build_content_changes(normalized_original, normalized_tailored),
        preservation_summary=preservation_summary,
        top_alignment_reasons=_top_alignment_reasons(keyword_evidence, entry_reviews),
        safety_notes=safety_notes,
        scores=scores,
    )


async def generate_tailoring_review(
    resume: ResumeData | dict | str,
    job_description: str,
) -> TailoringReviewResult:
    """Tailor a resume to a JD and return the review JSON without rendering PDF."""
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    normalized_resume = coerce_resume_data(resume)
    tailored_resume, keyword_targets = await _tailor_resume(
        resume=normalized_resume,
        job_description=job_description,
    )
    review_report = build_tailoring_review_report(
        original_resume=normalized_resume,
        tailored_resume=tailored_resume,
        job_description=job_description,
        keyword_targets=keyword_targets,
    )
    return TailoringReviewResult(
        tailored_resume=tailored_resume,
        keyword_targets=keyword_targets,
        review_report=review_report,
    )
