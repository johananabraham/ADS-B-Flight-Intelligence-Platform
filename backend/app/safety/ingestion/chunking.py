"""Deterministic, section-aware documents for the safety vector corpus."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from math import ceil
from uuid import UUID

from .contracts import EcfrSectionRecord, NtsbIncidentRecord


DEFAULT_MAX_TOKENS = 800
CHUNKER_VERSION = "1.0"
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
_TOKEN_CANDIDATE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass(frozen=True)
class VectorDocument:
    """One deterministic document and its filterable provenance metadata."""

    document_id: str
    text: str
    metadata: dict[str, str | int | float | bool]


def _estimated_token_count(text: str) -> int:
    """Estimate subword tokens locally without downloading a model vocabulary."""
    return sum(
        max(1, ceil(len(token.encode("utf-8")) / 4))
        for token in _TOKEN_CANDIDATE.findall(text)
    )


def _sentence_chunks(text: str, max_tokens: int) -> tuple[tuple[str, int, int], ...]:
    """Split at sentence boundaries and retain offsets in the normalized section."""
    sentences = _SENTENCE_BOUNDARY.split(text.strip())
    chunks: list[tuple[str, int, int]] = []
    current: list[str] = []
    current_start = 0
    current_end = 0
    cursor = 0

    for sentence in sentences:
        start = text.find(sentence, cursor)
        if start < 0:
            start = cursor
        end = start + len(sentence)
        candidate = " ".join((*current, sentence))
        if current and _estimated_token_count(candidate) > max_tokens:
            chunk_text = " ".join(current)
            chunks.append((chunk_text, current_start, current_end))
            current = [sentence]
            current_start = start
        else:
            if not current:
                current_start = start
            current.append(sentence)
        current_end = end
        cursor = end

    if current:
        chunks.append((" ".join(current), current_start, current_end))
    return tuple(chunks)


def _base_incident_metadata(
    record: NtsbIncidentRecord,
    *,
    source_run_id: UUID,
    source_sha256: str,
) -> dict[str, str | int | float | bool]:
    metadata: dict[str, str | int | float | bool] = {
        "ntsb_id": record.ntsb_id,
        "source_run_id": str(source_run_id),
        "source_sha256": source_sha256,
        "chunker_version": CHUNKER_VERSION,
        "fatal_injuries": record.fatal_injuries,
    }
    optional = {
        "event_date": record.event_date.isoformat() if record.event_date else None,
        "event_state": record.event_state,
        "aircraft_make": record.aircraft_make,
        "aircraft_model": record.aircraft_model,
        "weather_condition": record.weather_condition,
        "phase_of_flight": record.phase_of_flight,
        "source_url": record.source_url,
    }
    metadata.update({key: value for key, value in optional.items() if value is not None})
    return metadata


def chunk_incident_narrative(
    record: NtsbIncidentRecord,
    *,
    source_run_id: UUID,
    source_sha256: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> tuple[VectorDocument, ...]:
    """Create combined short documents or sentence-bounded section documents."""
    if max_tokens < 1:
        raise ValueError("max_tokens must be positive")
    sections = tuple(
        (name, text)
        for name, text in (
            ("factual_information", record.narrative),
            ("probable_cause", record.probable_cause),
        )
        if text
    )
    if not sections:
        return ()

    base_metadata = _base_incident_metadata(
        record,
        source_run_id=source_run_id,
        source_sha256=source_sha256,
    )
    combined = "\n\n".join(f"{name.replace('_', ' ').title()}:\n{text}" for name, text in sections)
    if _estimated_token_count(combined) <= max_tokens:
        return (
            VectorDocument(
                document_id=f"{record.ntsb_id}:combined:0",
                text=combined,
                metadata=base_metadata
                | {
                    "section": "combined",
                    "chunk_index": 0,
                    "estimated_token_count": _estimated_token_count(combined),
                },
            ),
        )

    documents: list[VectorDocument] = []
    for section, text in sections:
        heading = f"{section.replace('_', ' ').title()}:\n"
        content_budget = max(1, max_tokens - _estimated_token_count(heading))
        for index, (chunk, start, end) in enumerate(
            _sentence_chunks(text, content_budget)
        ):
            rendered = f"{heading}{chunk}"
            documents.append(
                VectorDocument(
                    document_id=f"{record.ntsb_id}:{section}:{index}",
                    text=rendered,
                    metadata=base_metadata
                    | {
                        "section": section,
                        "chunk_index": index,
                        "char_start": start,
                        "char_end": end,
                        "estimated_token_count": _estimated_token_count(rendered),
                    },
                )
            )
    return tuple(documents)


def regulation_document(
    record: EcfrSectionRecord,
    *,
    source_run_id: UUID,
    source_sha256: str,
) -> VectorDocument:
    """Create one versioned vector document for one dated CFR section."""
    text = f"{record.section_title}\n{record.section_text}"
    effective_date: date = record.effective_date
    return VectorDocument(
        document_id=(
            f"14:{record.cfr_part}:{record.cfr_section}:"
            f"{effective_date.isoformat()}"
        ),
        text=text,
        metadata={
            "cfr_title": record.cfr_title,
            "cfr_part": record.cfr_part,
            "cfr_section": record.cfr_section,
            "section_title": record.section_title,
            "effective_date": effective_date.isoformat(),
            "source_url": record.source_url,
            "source_run_id": str(source_run_id),
            "source_sha256": source_sha256,
            "chunker_version": CHUNKER_VERSION,
            "estimated_token_count": _estimated_token_count(text),
        },
    )
