"""Shared text helpers for resume tailoring and rendering."""

from __future__ import annotations

import re
from html import escape

_ZERO_WIDTH_RE = re.compile(r"[\u200B\u200C\u200D\u2060\uFEFF]")


def normalize_text_for_ats(text: str) -> tuple[str, dict[str, int]]:
    """Replace Unicode characters that commonly break ATS parsing."""
    replacements = {
        "em_dash": 0,
        "en_dash": 0,
        "smart_double_quote": 0,
        "smart_single_quote": 0,
        "ellipsis": 0,
        "zero_width": 0,
        "nbsp": 0,
    }

    normalized = text
    for old, new, key in (
        ("\u2014", "-", "em_dash"),
        ("\u2013", "-", "en_dash"),
        ("\u2026", "...", "ellipsis"),
        ("\u00a0", " ", "nbsp"),
    ):
        count = normalized.count(old)
        if count:
            normalized = normalized.replace(old, new)
            replacements[key] += count

    smart_double_count = sum(
        normalized.count(ch) for ch in ("\u201c", "\u201d", "\u201e", "\u201f")
    )
    if smart_double_count:
        for ch in ("\u201c", "\u201d", "\u201e", "\u201f"):
            normalized = normalized.replace(ch, '"')
        replacements["smart_double_quote"] = smart_double_count

    smart_single_count = sum(
        normalized.count(ch) for ch in ("\u2018", "\u2019", "\u201a", "\u201b")
    )
    if smart_single_count:
        for ch in ("\u2018", "\u2019", "\u201a", "\u201b"):
            normalized = normalized.replace(ch, "'")
        replacements["smart_single_quote"] = smart_single_count

    zero_width_matches = _ZERO_WIDTH_RE.findall(normalized)
    if zero_width_matches:
        replacements["zero_width"] = len(zero_width_matches)
        normalized = _ZERO_WIDTH_RE.sub("", normalized)

    return normalized, replacements


def compact_whitespace(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(str(value).split()).strip()


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = compact_whitespace(item)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def contains_term(text: str, term: str) -> bool:
    lowered = compact_whitespace(text).casefold()
    normalized_term = compact_whitespace(term).casefold()
    if not normalized_term:
        return False
    if re.fullmatch(r"[a-z0-9+#./-]+", normalized_term):
        return bool(
            re.search(
                rf"(?<![a-z0-9+#./-]){re.escape(normalized_term)}(?![a-z0-9+#./-])",
                lowered,
            )
        )
    return normalized_term in lowered


def has_any_term(text: str, terms: tuple[str, ...]) -> bool:
    lowered = compact_whitespace(text).casefold()
    return any(contains_term(lowered, term) for term in terms)


def join_contact(parts: list[str]) -> str:
    safe_parts = [escape(compact_whitespace(part)) for part in parts if compact_whitespace(part)]
    return ' <span class="separator">|</span> '.join(safe_parts) or "Not provided"


# Backward-compatible private aliases used by tests and legacy imports.
_compact_whitespace = compact_whitespace
_dedupe_preserve_order = dedupe_preserve_order
_contains_term = contains_term
_has_any_term = has_any_term
_join_contact = join_contact
