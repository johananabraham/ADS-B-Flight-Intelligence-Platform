"""Grounded citation contracts derived from completed safety tool calls."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any, Literal, Protocol
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompletedToolCall(Protocol):
    """Minimum completed tool-call shape needed for citation extraction."""

    name: str
    result: Any


class SourceSpan(BaseModel):
    """Exact retrieved text and its available source offsets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    section: str | None = None
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def require_ordered_offsets(self) -> "SourceSpan":
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise ValueError("char_end must not precede char_start")
        return self


class SourceCitation(BaseModel):
    """One retrieved source explicitly referenced by the final answer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: Literal["NTSB_INCIDENT", "ECFR_REGULATION"]
    label: str = Field(min_length=1)
    document_id: str | None = None
    source_url: str | None = None
    effective_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_run_id: str | None = None
    span: SourceSpan


def _is_referenced(answer: str, reference: str) -> bool:
    pattern = rf"(?<![A-Za-z0-9]){re.escape(reference)}(?![A-Za-z0-9])"
    return re.search(pattern, answer, re.IGNORECASE) is not None


def _safe_source_url(value: Any) -> str | None:
    if not value:
        return None
    url = str(value)
    parsed = urlsplit(url)
    return url if parsed.scheme in {"http", "https"} and parsed.netloc else None


def _citation_from_result(
    *,
    tool_name: str,
    item: dict[str, Any],
) -> SourceCitation | None:
    if tool_name == "search_incident_narratives":
        label = str(item.get("ntsb_id") or "")
        source_type = "NTSB_INCIDENT"
        text = str(item.get("excerpt") or "")
    elif tool_name == "search_faa_regulations":
        label = str(item.get("cfr_reference") or "")
        source_type = "ECFR_REGULATION"
        text = str(item.get("text_excerpt") or "")
    elif tool_name == "get_incident_detail":
        label = str(item.get("ntsb_id") or "")
        source_type = "NTSB_INCIDENT"
        investigation = item.get("investigation") or {}
        text = str(item.get("narrative") or investigation.get("probable_cause") or "")
    else:
        return None

    if not label or not text:
        return None
    return SourceCitation(
        source_type=source_type,
        label=label,
        document_id=item.get("document_id"),
        source_url=_safe_source_url(item.get("source_url")),
        effective_date=item.get("effective_date"),
        source_sha256=item.get("source_sha256"),
        source_run_id=item.get("source_run_id"),
        span=SourceSpan(
            section=item.get("section"),
            char_start=item.get("char_start"),
            char_end=item.get("char_end"),
            text=text,
        ),
    )


def extract_grounded_citations(
    answer: str,
    tool_calls: Iterable[CompletedToolCall],
) -> tuple[SourceCitation, ...]:
    """Return only retrieved sources explicitly referenced in the final answer."""
    citations: list[SourceCitation] = []
    seen: set[tuple[str, str]] = set()
    for tool_call in tool_calls:
        result = tool_call.result
        items = result.get("results", []) if isinstance(result, dict) else []
        if tool_call.name == "get_incident_detail" and isinstance(result, dict):
            items = [result]
        for item in items:
            if not isinstance(item, dict):
                continue
            citation = _citation_from_result(tool_name=tool_call.name, item=item)
            if citation is None or not _is_referenced(answer, citation.label):
                continue
            key = (citation.source_type, citation.label.casefold())
            if key not in seen:
                citations.append(citation)
                seen.add(key)
    return tuple(citations)
