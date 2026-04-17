"""Career Ops style job evaluation helpers.

This module translates the high-level A-F structure from the upstream
``career-ops`` repo into a backend-friendly, structured evaluator that can
return consistent JSON to the frontend.
"""

from __future__ import annotations

import copy
import json
import logging
import re
from collections import defaultdict
from statistics import mean
from typing import Any

from app.career_ops.market_data import fetch_market_signals
from app.llm import complete_json
from app.schemas.models import (
    CareerOpsEvaluationData,
    CareerOpsMarketData,
    CareerOpsScoreDimension,
    ResumeData,
    normalize_resume_data,
)

logger = logging.getLogger(__name__)

DEFAULT_DIMENSION_BLUEPRINT: list[dict[str, str]] = [
    {
        "key": "archetype_fit",
        "category": "A",
        "label": "Archetype Fit",
        "prompt_focus": "How well the role archetype matches the candidate's strongest lane.",
    },
    {
        "key": "role_scope_clarity",
        "category": "A",
        "label": "Role Scope Clarity",
        "prompt_focus": "How clearly the JD defines the role, remit, environment, and success scope.",
    },
    {
        "key": "hard_requirement_match",
        "category": "B",
        "label": "Hard Requirement Match",
        "prompt_focus": "How well the resume maps to explicit requirements in the JD.",
    },
    {
        "key": "gap_mitigation_strength",
        "category": "B",
        "label": "Gap Mitigation Strength",
        "prompt_focus": "How credibly adjacent experience can cover missing requirements.",
    },
    {
        "key": "seniority_alignment",
        "category": "C",
        "label": "Seniority Alignment",
        "prompt_focus": "How well the candidate's natural level matches the JD's level.",
    },
    {
        "key": "positioning_strategy",
        "category": "C",
        "label": "Positioning Strategy",
        "prompt_focus": "How strong the 'sell senior without lying' story is for this application.",
    },
    {
        "key": "comp_and_demand_signal",
        "category": "D",
        "label": "Comp and Demand Signal",
        "prompt_focus": "What can be inferred from the JD alone about compensation clarity and market demand.",
    },
    {
        "key": "resume_customization_leverage",
        "category": "E",
        "label": "Resume Customization Leverage",
        "prompt_focus": "How much the resume can be improved for the role without inventing facts.",
    },
    {
        "key": "linkedin_customization_leverage",
        "category": "E",
        "label": "LinkedIn Customization Leverage",
        "prompt_focus": "How much profile positioning can be improved for recruiter-facing discoverability.",
    },
    {
        "key": "interview_story_readiness",
        "category": "F",
        "label": "Interview Story Readiness",
        "prompt_focus": "How ready the candidate is with STAR stories and a strong case-study angle.",
    },
]

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]{2,}")
_NUMBER_RE = re.compile(r"\b(?:\d+%|\$\d+(?:[.,]\d+)?[KMB]?|\d+[KMB]?|\d+\+)\b")
_YEARS_RE = re.compile(r"(\d+)\+?\s+years?", re.IGNORECASE)

_STOPWORDS = {
    "about",
    "across",
    "after",
    "build",
    "building",
    "candidate",
    "company",
    "design",
    "engineer",
    "engineering",
    "experience",
    "looking",
    "platform",
    "product",
    "requirements",
    "responsibilities",
    "senior",
    "team",
    "work",
    "with",
    "your",
}

_KNOWN_KEYWORDS = [
    "Python",
    "FastAPI",
    "Django",
    "Flask",
    "API",
    "REST",
    "GraphQL",
    "Docker",
    "Kubernetes",
    "AWS",
    "GCP",
    "Azure",
    "Terraform",
    "CI/CD",
    "GitHub Actions",
    "PostgreSQL",
    "Redis",
    "Microservices",
    "LLM",
    "RAG",
    "Evals",
    "Prompting",
    "Agents",
    "Multi-agent",
    "Observability",
    "OpenAI",
]


def coerce_resume_data(resume: ResumeData | dict[str, Any] | str) -> ResumeData:
    """Normalize request input into the existing ResumeData schema."""
    if isinstance(resume, ResumeData):
        return resume

    if isinstance(resume, dict):
        payload = copy.deepcopy(resume)
        payload = normalize_resume_data(payload)
        return ResumeData.model_validate(payload)

    if not isinstance(resume, str):
        raise TypeError("resume must be a ResumeData object, dict, or string")

    text = resume.strip()
    if not text:
        raise ValueError("resume cannot be empty")

    if text.startswith("{"):
        payload = json.loads(text)
        payload = normalize_resume_data(payload)
        return ResumeData.model_validate(payload)

    return ResumeData(summary=text)


def resume_to_text(resume: ResumeData | dict[str, Any] | str) -> str:
    """Convert structured resume data into a readable, LLM-friendly text block."""
    data = coerce_resume_data(resume)
    parts: list[str] = []

    personal = data.personalInfo
    header_bits = [personal.name, personal.title, personal.location]
    header = " | ".join(bit for bit in header_bits if bit)
    if header:
        parts.append(header)

    if data.summary:
        parts.append(f"Summary:\n{data.summary}")

    if data.workExperience:
        experience_lines = ["Work Experience:"]
        for item in data.workExperience:
            line = f"- {item.title} @ {item.company} ({item.years})"
            if item.location:
                line += f" [{item.location}]"
            experience_lines.append(line)
            for bullet in item.description:
                experience_lines.append(f"  - {bullet}")
        parts.append("\n".join(experience_lines))

    if data.personalProjects:
        project_lines = ["Projects:"]
        for item in data.personalProjects:
            project_lines.append(f"- {item.name} — {item.role} ({item.years})")
            for bullet in item.description:
                project_lines.append(f"  - {bullet}")
        parts.append("\n".join(project_lines))

    if data.education:
        education_lines = ["Education:"]
        for item in data.education:
            education_lines.append(f"- {item.degree} @ {item.institution} ({item.years})")
            if item.description:
                education_lines.append(f"  - {item.description}")
        parts.append("\n".join(education_lines))

    additional = data.additional
    extra_lines = []
    if additional.technicalSkills:
        extra_lines.append("Technical Skills: " + ", ".join(additional.technicalSkills))
    if additional.languages:
        extra_lines.append("Languages: " + ", ".join(additional.languages))
    if additional.certificationsTraining:
        extra_lines.append(
            "Certifications: " + ", ".join(additional.certificationsTraining)
        )
    if additional.awards:
        extra_lines.append("Awards: " + ", ".join(additional.awards))
    if extra_lines:
        parts.append("\n".join(extra_lines))

    return "\n\n".join(part for part in parts if part).strip()


def extract_keyword_targets(job_description: str, limit: int = 12) -> list[str]:
    """Pull a compact keyword list from the JD for scoring and ATS emphasis."""
    text = job_description or ""
    lower = text.lower()
    keywords: list[str] = []

    for keyword in _KNOWN_KEYWORDS:
        if keyword.lower() in lower:
            keywords.append(keyword)

    for token in _TOKEN_RE.findall(text):
        normalized = token.strip(".,:;()[]{}")
        if len(normalized) < 4:
            continue
        lowered = normalized.lower()
        if lowered in _STOPWORDS:
            continue
        if normalized not in keywords:
            keywords.append(normalized)
        if len(keywords) >= limit:
            break

    return keywords[:limit]


def summarize_af_scores(dimensions: list[dict[str, Any]] | list[CareerOpsScoreDimension]) -> dict[str, float]:
    """Average dimension scores into their A-F block scores."""
    grouped: dict[str, list[float]] = defaultdict(list)
    for dimension in dimensions:
        if isinstance(dimension, CareerOpsScoreDimension):
            category = dimension.category
            score = dimension.score
        else:
            category = str(dimension.get("category", "")).upper()
            score = float(dimension.get("score", 0.0))
        if category in {"A", "B", "C", "D", "E", "F"}:
            grouped[category].append(score)

    scores: dict[str, float] = {}
    for category in ("A", "B", "C", "D", "E", "F"):
        values = grouped.get(category, [])
        scores[category] = round(mean(values), 2) if values else 0.0
    return scores


def build_job_evaluation_prompt(
    resume: ResumeData | dict[str, Any] | str,
    job_description: str,
) -> str:
    """Build the structured evaluator prompt."""
    normalized_resume = coerce_resume_data(resume)
    dimension_lines = "\n".join(
        f"- {item['category']}::{item['key']} — {item['label']}: {item['prompt_focus']}"
        for item in DEFAULT_DIMENSION_BLUEPRINT
    )

    return f"""
You are evaluating a job application using a Career Ops inspired A-F framework.

Score on a 0.0-5.0 scale and keep the reasoning grounded in the provided resume and JD.
Block D must only use evidence explicit in the JD. If salary, market demand, or compensation data
is not present, say that it is unclear instead of inventing facts.

Required blocks:
- Block A: role summary and archetype fit
- Block B: resume/JD match and gap mitigation
- Block C: seniority alignment and positioning strategy
- Block D: compensation/demand signal inferred only from the JD
- Block E: resume + LinkedIn customization leverage
- Block F: interview story readiness

Use exactly these 10 dimensions:
{dimension_lines}

Resume JSON:
{json.dumps(normalized_resume.model_dump(), indent=2, ensure_ascii=False)}

Job Description:
{job_description}

Return valid JSON only with this shape:
{{
  "executive_summary": "short paragraph",
  "archetype": "short archetype label",
  "dimensions": [
    {{
      "key": "archetype_fit",
      "category": "A",
      "label": "Archetype Fit",
      "score": 0.0,
      "rationale": "why",
      "evidence": ["resume proof point 1"],
      "risks": ["risk or gap"]
    }}
  ],
  "tailoring_priorities": ["top resume changes"],
  "interview_focus": ["top interview prep items"],
  "keyword_targets": ["ATS keyword", "ATS keyword"]
}}

Return valid JSON only.
""".strip()


def _score_label(score: float) -> str:
    if score >= 4.25:
        return "strong-match"
    if score >= 3.25:
        return "good-match"
    if score >= 2.5:
        return "stretch"
    return "low-match"


def infer_role_query(job_description: str) -> str:
    """Infer a compact search query for market lookups."""
    lines = [line.strip() for line in job_description.splitlines() if line.strip()]
    if lines and len(lines[0]) <= 90:
        return lines[0]

    lower = job_description.lower()
    if "solutions architect" in lower:
        return "Solutions Architect"
    if "product manager" in lower:
        return "Product Manager"
    if "ai engineer" in lower:
        return "AI Engineer"
    if "backend engineer" in lower:
        return "Backend Engineer"
    return "Software Engineer"


def infer_company_name(job_description: str) -> str | None:
    """Best-effort company extraction from the JD headline."""
    first_line = next((line.strip() for line in job_description.splitlines() if line.strip()), "")
    match = re.search(r"\bat\s+([A-Z][A-Za-z0-9&.\- ]+)", first_line)
    if match:
        return match.group(1).strip()
    return None


def _apply_market_data_to_dimensions(
    dimensions: list[CareerOpsScoreDimension],
    market_data: CareerOpsMarketData | None,
) -> list[CareerOpsScoreDimension]:
    """Fold live market signals into the Block D dimension."""
    if market_data is None:
        return dimensions

    updated: list[CareerOpsScoreDimension] = []
    for dimension in dimensions:
        if dimension.key != "comp_and_demand_signal":
            updated.append(dimension)
            continue

        evidence = list(dimension.evidence)
        risks = list(dimension.risks)
        if market_data.salary_mentions:
            evidence.append("Live salary mentions: " + ", ".join(market_data.salary_mentions[:3]))
        if market_data.sources:
            evidence.append(f"Live sources gathered: {len(market_data.sources)}")
        else:
            risks.append("No live market sources were available for Block D.")

        updated.append(
            CareerOpsScoreDimension(
                key=dimension.key,
                category=dimension.category,
                label=dimension.label,
                score=_score(max(dimension.score, 3.2 if market_data.sources else dimension.score)),
                rationale=f"{dimension.rationale} {market_data.compensation_summary} {market_data.demand_summary}".strip(),
                evidence=evidence,
                risks=risks,
            )
        )
    return updated


def _infer_archetype(job_description: str) -> str:
    lower = job_description.lower()
    if any(token in lower for token in ("multi-agent", "agentic", "agents", "orchestration")):
        return "agentic-systems"
    if any(token in lower for token in ("llmops", "rag", "evals", "observability", "prompt")):
        return "llmops-platform"
    if any(token in lower for token in ("solution architect", "pre-sales", "client-facing", "integration")):
        return "solutions-architecture"
    if any(token in lower for token in ("product manager", "product strategy", "roadmap", "discovery")):
        return "product"
    if any(token in lower for token in ("change management", "adoption", "transformation")):
        return "transformation"
    if any(token in lower for token in ("backend", "platform", "api", "microservices", "infra")):
        return "platform-engineering"
    return "generalist-tech"


def _extract_years_target(job_description: str) -> int | None:
    match = _YEARS_RE.search(job_description)
    if not match:
        return None
    return int(match.group(1))


def _infer_resume_seniority(resume_text: str) -> float:
    lower = resume_text.lower()
    if "principal" in lower or "staff" in lower or "director" in lower:
        return 5.0
    if "senior" in lower or "lead" in lower or "manager" in lower:
        return 4.0
    if "junior" in lower or "associate" in lower:
        return 2.0
    return 3.0


def _score(value: float) -> float:
    return round(max(0.0, min(5.0, value)), 2)


def _keyword_overlap(resume_text: str, keyword_targets: list[str]) -> tuple[list[str], float]:
    lower_resume = resume_text.lower()
    matched = [keyword for keyword in keyword_targets if keyword.lower() in lower_resume]
    overlap = len(matched) / max(1, len(keyword_targets))
    return matched, overlap


def _heuristic_dimensions(
    resume_data: ResumeData,
    job_description: str,
    keyword_targets: list[str],
) -> list[CareerOpsScoreDimension]:
    """Build a deterministic fallback when the LLM is unavailable."""
    resume_text = resume_to_text(resume_data)
    matched_keywords, overlap = _keyword_overlap(resume_text, keyword_targets)
    metrics_count = len(_NUMBER_RE.findall(resume_text))
    clarity_signals = sum(
        1
        for token in ("requirements", "responsibilities", "you will", "we are looking", "preferred")
        if token in job_description.lower()
    )
    years_target = _extract_years_target(job_description)
    years_signal = 0.0
    if years_target is not None:
        years_signal = 0.5 if metrics_count else 0.0
    resume_seniority = _infer_resume_seniority(resume_text)
    jd_seniority = _infer_resume_seniority(job_description)
    salary_explicit = bool(re.search(r"[$€£]\s?\d", job_description))
    missing_keywords = [keyword for keyword in keyword_targets if keyword not in matched_keywords]

    dimension_map = {
        "archetype_fit": (
            _score(2.5 + (overlap * 2.2)),
            f"Detected archetype {_infer_archetype(job_description)} with {len(matched_keywords)} matched keyword targets.",
            matched_keywords[:3] or ["General backend/platform signals overlap."],
            missing_keywords[:2],
        ),
        "role_scope_clarity": (
            _score(2.2 + (clarity_signals * 0.65)),
            "Estimated from how explicit the JD is about responsibilities, requirements, and scope.",
            [f"JD clarity signals found: {clarity_signals}"],
            [] if clarity_signals >= 2 else ["JD leaves team scope or impact area somewhat vague."],
        ),
        "hard_requirement_match": (
            _score(1.6 + (overlap * 3.2)),
            "Scored from keyword overlap between the JD and the resume text.",
            matched_keywords[:5] or ["Few explicit keyword overlaps were detected."],
            missing_keywords[:3],
        ),
        "gap_mitigation_strength": (
            _score(2.0 + (overlap * 1.4) + min(metrics_count, 6) * 0.18),
            "Quantified achievements improve the ability to bridge adjacent gaps without overstating experience.",
            [f"Quantified proof points found: {metrics_count}"],
            missing_keywords[:2],
        ),
        "seniority_alignment": (
            _score(5.0 - abs(jd_seniority - resume_seniority) * 1.2 + years_signal),
            "Compared seniority cues in the JD and the candidate profile.",
            [f"Resume seniority estimate: {resume_seniority}", f"JD seniority estimate: {jd_seniority}"],
            [] if abs(jd_seniority - resume_seniority) <= 1 else ["Potential level mismatch."],
        ),
        "positioning_strategy": (
            _score(2.4 + (overlap * 1.4) + min(metrics_count, 6) * 0.2),
            "Measured by the strength of evidence available for a credible positioning story.",
            [f"Metrics-rich bullets: {metrics_count}", f"Matched keywords: {len(matched_keywords)}"],
            [] if metrics_count >= 2 else ["Resume needs more quantified examples for stronger positioning."],
        ),
        "comp_and_demand_signal": (
            _score(3.6 if salary_explicit else 2.9 + min(len(keyword_targets), 6) * 0.12),
            "Block D is intentionally conservative because this backend does not run live market web search.",
            ["Salary range explicitly present in JD."] if salary_explicit else ["No salary range in JD; demand signal inferred from role specificity only."],
            [] if salary_explicit else ["Comp and demand should be web-verified in a later iteration."],
        ),
        "resume_customization_leverage": (
            _score(2.6 + (len(missing_keywords) * 0.12) + (len(matched_keywords) * 0.1)),
            "How much truthful improvement room exists in the resume itself.",
            [f"Matched keywords to foreground: {', '.join(matched_keywords[:4]) or 'none'}"],
            [] if missing_keywords else ["Little additional ATS leverage remains beyond current alignment."],
        ),
        "linkedin_customization_leverage": (
            _score(2.7 + (len(keyword_targets) * 0.1)),
            "Recruiter-facing positioning usually has room to mirror the JD's strongest language.",
            [f"Keyword targets available for headline/about refresh: {len(keyword_targets)}"],
            [],
        ),
        "interview_story_readiness": (
            _score(2.3 + min(metrics_count, 8) * 0.28),
            "Quantified bullets and project depth are the best local proxy for strong STAR stories.",
            [f"Story-ready metric count: {metrics_count}"],
            [] if metrics_count >= 3 else ["Prepare additional STAR stories with measurable outcomes."],
        ),
    }

    dimensions: list[CareerOpsScoreDimension] = []
    for item in DEFAULT_DIMENSION_BLUEPRINT:
        score, rationale, evidence, risks = dimension_map[item["key"]]
        dimensions.append(
            CareerOpsScoreDimension(
                key=item["key"],
                category=item["category"],
                label=item["label"],
                score=score,
                rationale=rationale,
                evidence=[str(entry) for entry in evidence],
                risks=[str(entry) for entry in risks if entry],
            )
        )
    return dimensions


def _normalize_dimension_payload(
    raw_dimensions: list[dict[str, Any]] | None,
    fallback_dimensions: list[CareerOpsScoreDimension],
) -> list[CareerOpsScoreDimension]:
    """Normalize LLM output and fill any missing dimensions from fallback values."""
    fallback_by_key = {dimension.key: dimension for dimension in fallback_dimensions}
    dimensions: list[CareerOpsScoreDimension] = []
    raw_by_key = {
        str(item.get("key")): item
        for item in (raw_dimensions or [])
        if isinstance(item, dict) and item.get("key")
    }

    for blueprint in DEFAULT_DIMENSION_BLUEPRINT:
        fallback = fallback_by_key[blueprint["key"]]
        raw = raw_by_key.get(blueprint["key"], {})
        dimensions.append(
            CareerOpsScoreDimension(
                key=blueprint["key"],
                category=blueprint["category"],
                label=str(raw.get("label") or blueprint["label"]),
                score=_score(float(raw.get("score", fallback.score))),
                rationale=str(raw.get("rationale") or fallback.rationale),
                evidence=[
                    str(entry)
                    for entry in (raw.get("evidence") or fallback.evidence)
                    if str(entry).strip()
                ],
                risks=[
                    str(entry)
                    for entry in (raw.get("risks") or fallback.risks)
                    if str(entry).strip()
                ],
            )
        )

    return dimensions


async def evaluate_job_fit(
    resume: ResumeData | dict[str, Any] | str,
    job_description: str,
) -> CareerOpsEvaluationData:
    """Evaluate a resume/JD pair using the structured A-F scoring model."""
    if not job_description or not job_description.strip():
        raise ValueError("job_description cannot be empty")

    resume_data = coerce_resume_data(resume)
    keyword_targets = extract_keyword_targets(job_description)
    fallback_dimensions = _heuristic_dimensions(
        resume_data=resume_data,
        job_description=job_description,
        keyword_targets=keyword_targets,
    )

    raw_result: dict[str, Any] = {}
    try:
        prompt = build_job_evaluation_prompt(resume=resume_data, job_description=job_description)
        raw_result = await complete_json(
            prompt=prompt,
            system_prompt=(
                "You are a truthful job-search strategist. "
                "Never invent compensation facts or experience not present in the resume."
            ),
            max_tokens=2400,
        )
    except Exception as exc:
        logger.warning("Career Ops evaluator fell back to heuristic scoring: %s", exc)

    dimensions = _normalize_dimension_payload(
        raw_dimensions=raw_result.get("dimensions") if isinstance(raw_result, dict) else None,
        fallback_dimensions=fallback_dimensions,
    )
    market_data = await fetch_market_signals(
        infer_role_query(job_description),
        company_name=infer_company_name(job_description),
    )
    dimensions = _apply_market_data_to_dimensions(dimensions, market_data)
    af_scores = summarize_af_scores(dimensions)
    overall_score = _score(mean(dimension.score for dimension in dimensions))
    overall_label = str(raw_result.get("overall_label") or _score_label(overall_score))
    executive_summary = str(
        raw_result.get("executive_summary")
        or f"{overall_label.replace('-', ' ').title()} based on {len(keyword_targets)} keyword targets and {len(dimensions)} scored dimensions."
    )
    archetype = str(raw_result.get("archetype") or _infer_archetype(job_description))

    tailoring_priorities = [
        str(entry)
        for entry in (raw_result.get("tailoring_priorities") or [])
        if str(entry).strip()
    ]
    if not tailoring_priorities:
        matched_keywords, _ = _keyword_overlap(resume_to_text(resume_data), keyword_targets)
        tailoring_priorities = [
            f"Move these matched keywords higher in the resume summary: {', '.join(matched_keywords[:4])}"
            if matched_keywords
            else "Tighten the summary around the JD's core stack and business scope.",
            "Prioritize quantified bullets that directly mirror the job's top responsibilities.",
            "Reorder visible skills so the strongest matched technologies appear first.",
        ]

    interview_focus = [
        str(entry)
        for entry in (raw_result.get("interview_focus") or [])
        if str(entry).strip()
    ]
    if not interview_focus:
        interview_focus = [
            "Prepare one architecture or migration story with measurable impact.",
            "Prepare one collaboration story that shows scope, influence, and trade-offs.",
            "Prepare one gap-mitigation answer for the least-matched requirement.",
        ]

    returned_keywords = [
        str(entry)
        for entry in (raw_result.get("keyword_targets") or keyword_targets)
        if str(entry).strip()
    ]

    return CareerOpsEvaluationData(
        overall_score=overall_score,
        overall_label=overall_label,
        executive_summary=executive_summary,
        archetype=archetype,
        af_scores=af_scores,
        dimensions=dimensions,
        tailoring_priorities=tailoring_priorities,
        interview_focus=interview_focus,
        keyword_targets=returned_keywords[:12],
        market_data=market_data,
    )
