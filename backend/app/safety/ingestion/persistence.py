"""Transactional, idempotent persistence for parsed safety sources."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ...models import (
    Incident,
    Regulation,
    SafetyIngestionRejectionRecord,
    SafetyIngestionRunRecord,
)
from .contracts import EcfrSectionRecord, NtsbIncidentRecord, ParsedSource, ValidationReport


@dataclass(frozen=True)
class IngestionOutcome:
    """Database outcome for one parsed source artifact."""

    run_id: UUID
    applied: bool
    record_count: int
    rejection_count: int


def ingestion_run_id(report: ValidationReport) -> UUID:
    """Return a stable identity for one source hash and parser version."""
    identity = ":".join(
        (report.source_kind.value, report.source_sha256, report.parser_version)
    )
    return uuid5(NAMESPACE_URL, f"adsb-safety-ingestion:{identity}")


def build_run_insert(report: ValidationReport, *, ingested_at: datetime):
    """Build an idempotent source-manifest insert."""
    run_id = ingestion_run_id(report)
    return (
        insert(SafetyIngestionRunRecord)
        .values(
            run_id=run_id,
            source_kind=report.source_kind.value,
            source_uri=report.source_uri,
            source_sha256=report.source_sha256,
            source_bytes=report.source_bytes,
            retrieved_at=report.retrieved_at,
            effective_date=report.effective_date,
            parser_version=report.parser_version,
            parameters=report.parameters,
            source_record_count=report.source_record_count,
            parsed_record_count=report.parsed_record_count,
            rejected_record_count=report.rejected_record_count,
            duplicate_identifier_count=report.duplicate_identifier_count,
            null_rates=report.null_rates,
            ingested_at=ingested_at,
        )
        .on_conflict_do_nothing(
            index_elements=["source_kind", "source_sha256", "parser_version"]
        )
        .returning(SafetyIngestionRunRecord.run_id)
    )


def build_rejections_insert(report: ValidationReport, run_id: UUID):
    """Build dead-letter metadata for source rows that need review."""
    values = [
        {
            "run_id": run_id,
            "source_index": issue.source_index,
            "source_identifier": issue.source_identifier,
            "code": issue.code,
            "message": issue.message,
        }
        for issue in report.issues
    ]
    if not values:
        return None
    return (
        insert(SafetyIngestionRejectionRecord)
        .values(values)
        .on_conflict_do_nothing(
            index_elements=["run_id", "source_index", "code"]
        )
    )


def build_incidents_upsert(records: tuple[NtsbIncidentRecord, ...], run_id: UUID):
    """Build one parameterized bulk upsert for canonical incident rows."""
    values = [record.model_dump() | {"source_run_id": run_id} for record in records]
    if not values:
        return None
    statement = insert(Incident).values(values)
    updated_columns = {
        column: getattr(statement.excluded, column)
        for column in values[0]
        if column != "ntsb_id"
    }
    return statement.on_conflict_do_update(
        index_elements=["ntsb_id"], set_=updated_columns
    )


def build_regulations_upsert(records: tuple[EcfrSectionRecord, ...], run_id: UUID):
    """Build a dated upsert without overwriting older CFR snapshots."""
    values = [record.model_dump() | {"source_run_id": run_id} for record in records]
    if not values:
        return None
    statement = insert(Regulation).values(values)
    updated_columns = {
        column: getattr(statement.excluded, column)
        for column in ("section_title", "section_text", "source_url", "source_run_id")
    }
    return statement.on_conflict_do_update(
        index_elements=["cfr_title", "cfr_part", "cfr_section", "effective_date"],
        set_=updated_columns,
    )


def _persist(
    db: Session,
    parsed: ParsedSource,
    build_records_statement,
    *,
    ingested_at: datetime | None = None,
) -> IngestionOutcome:
    timestamp = ingested_at or datetime.now(timezone.utc)
    run_id = ingestion_run_id(parsed.report)
    inserted_run_id = db.execute(
        build_run_insert(parsed.report, ingested_at=timestamp)
    ).scalar_one_or_none()
    if inserted_run_id is None:
        return IngestionOutcome(
            run_id=run_id,
            applied=False,
            record_count=len(parsed.records),
            rejection_count=len(parsed.report.issues),
        )

    rejection_statement = build_rejections_insert(parsed.report, run_id)
    if rejection_statement is not None:
        db.execute(rejection_statement)
    records_statement = build_records_statement(parsed.records, run_id)
    if records_statement is not None:
        db.execute(records_statement)
    return IngestionOutcome(
        run_id=run_id,
        applied=True,
        record_count=len(parsed.records),
        rejection_count=len(parsed.report.issues),
    )


def persist_ntsb_source(
    db: Session,
    parsed: ParsedSource[NtsbIncidentRecord],
    *,
    ingested_at: datetime | None = None,
) -> IngestionOutcome:
    """Persist one parsed NTSB artifact in the caller's transaction."""
    return _persist(
        db,
        parsed,
        build_incidents_upsert,
        ingested_at=ingested_at,
    )


def persist_ecfr_source(
    db: Session,
    parsed: ParsedSource[EcfrSectionRecord],
    *,
    ingested_at: datetime | None = None,
) -> IngestionOutcome:
    """Persist one parsed eCFR artifact in the caller's transaction."""
    return _persist(
        db,
        parsed,
        build_regulations_upsert,
        ingested_at=ingested_at,
    )
