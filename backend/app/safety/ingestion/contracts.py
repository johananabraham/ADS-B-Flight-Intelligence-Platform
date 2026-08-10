"""Canonical records and lineage contracts for safety-source ingestion."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator


PARSER_VERSION = "1.0"
MAX_SOURCE_BYTES = 25 * 1024 * 1024


class SourceKind(StrEnum):
    """Supported authoritative source artifact types."""

    NTSB_CAROL_JSON = "NTSB_CAROL_JSON"
    ECFR_PART_XML = "ECFR_PART_XML"


class SourceArtifact(BaseModel):
    """Exact bytes and retrieval metadata supplied to a parser."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: SourceKind
    source_uri: str = Field(min_length=1, max_length=2_000)
    retrieved_at: datetime
    content: bytes
    effective_date: date | None = None
    parameters: dict[str, str | int] = Field(default_factory=dict)

    @field_validator("retrieved_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value

    @field_validator("content")
    @classmethod
    def bound_content(cls, value: bytes) -> bytes:
        if not value:
            raise ValueError("source content cannot be empty")
        if len(value) > MAX_SOURCE_BYTES:
            raise ValueError(f"source content exceeds {MAX_SOURCE_BYTES} bytes")
        return value

    @property
    def content_sha256(self) -> str:
        return sha256(self.content).hexdigest()


class ValidationIssue(BaseModel):
    """One rejected or suspicious source record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_index: int = Field(ge=0)
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=1_000)
    source_identifier: str | None = Field(default=None, max_length=100)


class ValidationReport(BaseModel):
    """Deterministic data-quality result for one source artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    manifest_version: str = "1.0"
    parser_version: str = PARSER_VERSION
    source_kind: SourceKind
    source_uri: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_bytes: int = Field(gt=0)
    retrieved_at: datetime
    effective_date: date | None = None
    parameters: dict[str, str | int] = Field(default_factory=dict)
    source_record_count: int = Field(ge=0)
    parsed_record_count: int = Field(ge=0)
    rejected_record_count: int = Field(ge=0)
    duplicate_identifier_count: int = Field(ge=0)
    null_rates: dict[str, float] = Field(default_factory=dict)
    issues: tuple[ValidationIssue, ...] = ()

    @field_validator("retrieved_at")
    @classmethod
    def require_report_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")
        return value


class NtsbIncidentRecord(BaseModel):
    """Canonical subset used by the structured incident store."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ntsb_id: str = Field(min_length=3, max_length=20)
    event_date: date | None = None
    event_city: str | None = Field(default=None, max_length=100)
    event_state: str | None = Field(default=None, max_length=50)
    event_country: str | None = Field(default=None, max_length=100)
    aircraft_make: str | None = Field(default=None, max_length=100)
    aircraft_model: str | None = Field(default=None, max_length=100)
    registration_number: str | None = Field(default=None, max_length=20)
    fatal_injuries: int = Field(default=0, ge=0)
    serious_injuries: int = Field(default=0, ge=0)
    minor_injuries: int = Field(default=0, ge=0)
    uninjured: int = Field(default=0, ge=0)
    weather_condition: str | None = Field(default=None, max_length=20)
    phase_of_flight: str | None = Field(default=None, max_length=100)
    probable_cause: str | None = None
    narrative: str | None = None
    source_url: str | None = Field(default=None, max_length=2_000)


class EcfrSectionRecord(BaseModel):
    """One dated 14 CFR section from the official eCFR XML."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    cfr_title: int = 14
    cfr_part: int = Field(gt=0)
    cfr_section: str = Field(pattern=r"^\d+\.\d+[A-Za-z0-9-]*$")
    section_title: str = Field(min_length=1, max_length=500)
    section_text: str = Field(min_length=1)
    effective_date: date
    source_url: str = Field(min_length=1, max_length=500)


RecordT = TypeVar("RecordT", bound=BaseModel)


class ParsedSource(BaseModel, Generic[RecordT]):
    """Canonical records plus their inseparable validation report."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    records: tuple[RecordT, ...]
    report: ValidationReport
