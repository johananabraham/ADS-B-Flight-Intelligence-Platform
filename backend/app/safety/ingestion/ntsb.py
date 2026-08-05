"""Parser for JSON exported by the official NTSB CAROL application."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from pydantic import ValidationError

from .contracts import (
    NtsbIncidentRecord,
    ParsedSource,
    SourceArtifact,
    SourceKind,
    ValidationIssue,
    ValidationReport,
)


def _first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, ""):
            return value
    return None


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    return cleaned or None


def _date(value: Any) -> date | None:
    text = _clean_text(value)
    if text is None:
        return None
    normalized = text.removesuffix("Z").split("T", 1)[0]
    for format_string in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(normalized, format_string).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported event date: {text}")


def _nonnegative_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    parsed = int(value)
    if parsed < 0:
        raise ValueError("injury count cannot be negative")
    return parsed


def _source_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = next(
            (
                value
                for key in ("results", "data", "investigations")
                if isinstance((value := payload.get(key)), list)
            ),
            None,
        )
        if records is None:
            raise ValueError("CAROL JSON must contain results, data, or investigations")
    else:
        raise ValueError("CAROL JSON root must be an object or array")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("every CAROL result must be an object")
    return records


def _first_aircraft(record: dict[str, Any]) -> dict[str, Any]:
    value = _first(record, "aircraft", "aircrafts", "aircraftData")
    if isinstance(value, list):
        return value[0] if value and isinstance(value[0], dict) else {}
    return value if isinstance(value, dict) else {}


def _parse_record(record: dict[str, Any]) -> NtsbIncidentRecord:
    aircraft = _first_aircraft(record)
    return NtsbIncidentRecord(
        ntsb_id=_clean_text(
            _first(record, "ntsbNumber", "ntsb_id", "ntsbId", "event_id")
        ),
        event_date=_date(_first(record, "eventDate", "event_date")),
        event_city=_clean_text(_first(record, "eventCity", "event_city", "city")),
        event_state=_clean_text(
            _first(record, "eventStateOrRegion", "eventState", "event_state", "state")
        ),
        event_country=_clean_text(
            _first(record, "eventCountry", "event_country", "country")
        ),
        aircraft_make=_clean_text(
            _first(aircraft, "make", "aircraftMake")
            or _first(record, "aircraftMake", "aircraft_make", "make")
        ),
        aircraft_model=_clean_text(
            _first(aircraft, "model", "aircraftModel")
            or _first(record, "aircraftModel", "aircraft_model", "model")
        ),
        registration_number=_clean_text(
            _first(aircraft, "registration", "registrationNumber")
            or _first(record, "registrationNumber", "registration_number")
        ),
        fatal_injuries=_nonnegative_int(
            _first(record, "fatalInjuryCount", "fatalInjuries", "fatal_injuries")
        ),
        serious_injuries=_nonnegative_int(
            _first(record, "seriousInjuryCount", "seriousInjuries", "serious_injuries")
        ),
        minor_injuries=_nonnegative_int(
            _first(record, "minorInjuryCount", "minorInjuries", "minor_injuries")
        ),
        uninjured=_nonnegative_int(
            _first(record, "uninjuredCount", "uninjured")
        ),
        weather_condition=_clean_text(
            _first(record, "weatherCondition", "weather_condition")
        ),
        phase_of_flight=_clean_text(
            _first(record, "broadPhaseOfFlight", "phaseOfFlight", "phase_of_flight")
        ),
        probable_cause=_clean_text(_first(record, "probableCause", "probable_cause")),
        narrative=_clean_text(
            _first(record, "narrative", "factualNarrative", "factual_narrative")
        ),
        source_url=_clean_text(
            _first(record, "investigationUrl", "sourceUrl", "source_url")
        ),
    )


def _null_rates(records: list[NtsbIncidentRecord]) -> dict[str, float]:
    if not records:
        return {}
    fields = ("event_date", "aircraft_make", "aircraft_model", "probable_cause")
    return {
        field: round(sum(getattr(record, field) is None for record in records) / len(records), 4)
        for field in fields
    }


def parse_ntsb_carol_json(
    artifact: SourceArtifact,
) -> ParsedSource[NtsbIncidentRecord]:
    """Parse, validate, and de-duplicate one official CAROL JSON export."""
    if artifact.kind is not SourceKind.NTSB_CAROL_JSON:
        raise ValueError("artifact kind must be NTSB_CAROL_JSON")
    try:
        payload = json.loads(artifact.content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid UTF-8 CAROL JSON: {error}") from error

    source_records = _source_records(payload)
    parsed_by_id: dict[str, NtsbIncidentRecord] = {}
    issues: list[ValidationIssue] = []
    duplicate_count = 0
    for index, source_record in enumerate(source_records):
        source_identifier = _clean_text(
            _first(source_record, "ntsbNumber", "ntsb_id", "ntsbId", "event_id")
        )
        try:
            record = _parse_record(source_record)
        except (TypeError, ValueError, ValidationError) as error:
            issues.append(
                ValidationIssue(
                    source_index=index,
                    source_identifier=source_identifier,
                    code="INVALID_RECORD",
                    message=str(error),
                )
            )
            continue
        if record.ntsb_id in parsed_by_id:
            duplicate_count += 1
            issues.append(
                ValidationIssue(
                    source_index=index,
                    source_identifier=record.ntsb_id,
                    code="DUPLICATE_IDENTIFIER",
                    message="duplicate NTSB number; first valid record retained",
                )
            )
            continue
        parsed_by_id[record.ntsb_id] = record

    records = list(parsed_by_id.values())
    report = ValidationReport(
        source_kind=artifact.kind,
        source_uri=artifact.source_uri,
        source_sha256=artifact.content_sha256,
        source_bytes=len(artifact.content),
        source_record_count=len(source_records),
        parsed_record_count=len(records),
        rejected_record_count=len(source_records) - len(records) - duplicate_count,
        duplicate_identifier_count=duplicate_count,
        null_rates=_null_rates(records),
        issues=tuple(issues),
    )
    return ParsedSource[NtsbIncidentRecord](records=tuple(records), report=report)
