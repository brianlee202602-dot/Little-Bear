"""Citation validation helpers for query answers."""

from __future__ import annotations

import re
from typing import Literal

from app.modules.query.schemas import QueryAllowedCandidate, _CitationValidationResult

SOURCE_REF_PATTERN = re.compile(r"\[source:([^\]\s]+)\]")
SOURCE_REF_DISPLAY_PATTERN = re.compile(r"\s*\[source:[^\]\s]+\]")
REFERENCE_SOURCE_LINE_PATTERN = re.compile(
    r"(?:\n\s*)?参考来源：\s*(?:\[source:[^\]\s]+\]\s*)+",
    re.MULTILINE,
)
SOURCE_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def validate_answer_citations(
    answer: str,
    *,
    allowed_source_ids: tuple[str, ...],
) -> _CitationValidationResult:
    referenced = tuple(dict.fromkeys(SOURCE_REF_PATTERN.findall(answer)))
    allowed = set(allowed_source_ids)
    if not referenced:
        return _CitationValidationResult(
            valid=False,
            degrade_reason="citation_missing",
            referenced_source_ids=(),
            invalid_source_ids=(),
            allowed_source_count=len(allowed),
        )
    invalid_format = tuple(
        source_id for source_id in referenced if not SOURCE_ID_PATTERN.fullmatch(source_id)
    )
    if invalid_format:
        return _CitationValidationResult(
            valid=False,
            degrade_reason="citation_invalid_format",
            referenced_source_ids=referenced,
            invalid_source_ids=invalid_format,
            allowed_source_count=len(allowed),
        )
    invalid = tuple(source_id for source_id in referenced if source_id not in allowed)
    if invalid:
        return _CitationValidationResult(
            valid=False,
            degrade_reason="citation_unauthorized",
            referenced_source_ids=referenced,
            invalid_source_ids=invalid,
            allowed_source_count=len(allowed),
        )
    return _CitationValidationResult(
        valid=True,
        degrade_reason="",
        referenced_source_ids=referenced,
        invalid_source_ids=(),
        allowed_source_count=len(allowed),
    )


def append_reference_sources(
    answer: str,
    *,
    allowed_candidates: tuple[QueryAllowedCandidate, ...],
    max_sources: int = 3,
) -> str:
    answer = answer.strip()
    if not answer or not allowed_candidates:
        return answer
    source_ids: list[str] = []
    seen: set[str] = set()
    for allowed in allowed_candidates:
        source_id = allowed.candidate.chunk_id
        if source_id in seen:
            continue
        seen.add(source_id)
        source_ids.append(source_id)
        if len(source_ids) >= max_sources:
            break
    if not source_ids:
        return answer
    source_refs = " ".join(f"[source:{source_id}]" for source_id in source_ids)
    return f"{answer}\n\n参考来源：{source_refs}"


def strip_source_refs_for_display(answer: str) -> str:
    without_reference_line = REFERENCE_SOURCE_LINE_PATTERN.sub("", answer)
    without_inline_refs = SOURCE_REF_DISPLAY_PATTERN.sub("", without_reference_line)
    lines = [line.rstrip() for line in without_inline_refs.splitlines()]
    compact_lines: list[str] = []
    previous_blank = False
    for line in lines:
        blank = not line.strip()
        if blank and previous_blank:
            continue
        compact_lines.append(line)
        previous_blank = blank
    return "\n".join(compact_lines).strip()


def citation_validation_summary(
    validation: _CitationValidationResult,
    *,
    final_degrade_reason: str,
) -> dict[str, object]:
    summary = validation.summary()
    if final_degrade_reason != validation.degrade_reason:
        summary["original_degrade_reason"] = validation.degrade_reason
        summary["degrade_reason"] = final_degrade_reason
        summary["auto_attached_sources"] = True
    return summary


def citation_validation_risk_level(reason: str) -> Literal["medium", "high", "critical"]:
    if reason == "citation_unauthorized":
        return "high"
    return "medium"
