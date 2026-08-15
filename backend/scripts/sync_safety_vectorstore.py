#!/usr/bin/env python3
"""Build the versioned safety vector corpus and verify SQL/vector consistency."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from sqlalchemy import func, or_, select

from app.core.database import SessionLocal
from app.core.vectorstore import (
    add_faa_regulations,
    add_incident_narratives,
    delete_incident_narratives,
    get_faa_regulations_collection,
    get_incident_narratives_collection,
)
from app.models import Incident, Regulation, SafetyIngestionRunRecord
from app.safety.ingestion import (
    EcfrSectionRecord,
    NtsbIncidentRecord,
    VectorDocument,
    chunk_incident_narrative,
    compare_corpus_lineage,
    indexed_lineage,
    regulation_document,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--batch-size", type=int, default=100)
    return parser.parse_args()


def _flush_incidents(documents: Sequence[VectorDocument]) -> None:
    if not documents:
        return
    add_incident_narratives(
        ids=[document.document_id for document in documents],
        documents=[document.text for document in documents],
        metadatas=[document.metadata for document in documents],
    )


def _flush_regulations(documents: Sequence[VectorDocument]) -> None:
    if not documents:
        return
    add_faa_regulations(
        ids=[document.document_id for document in documents],
        documents=[document.text for document in documents],
        metadatas=[document.metadata for document in documents],
    )


def sync_corpus(*, check_only: bool, batch_size: int) -> dict[str, object]:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    expected_incidents: dict[str, str] = {}
    expected_regulations: dict[str, str] = {}
    incident_batch: list[VectorDocument] = []
    regulation_batch: list[VectorDocument] = []

    with SessionLocal() as db:
        unversioned_incidents = db.scalar(
            select(func.count()).select_from(Incident).where(
                Incident.source_run_id.is_(None),
                or_(Incident.narrative.isnot(None), Incident.probable_cause.isnot(None)),
            )
        )
        unversioned_regulations = db.scalar(
            select(func.count()).select_from(Regulation).where(
                Regulation.source_run_id.is_(None)
            )
        )

        incident_rows = db.execute(
            select(Incident, SafetyIngestionRunRecord.source_sha256)
            .join(
                SafetyIngestionRunRecord,
                Incident.source_run_id == SafetyIngestionRunRecord.run_id,
            )
            .where(
                or_(Incident.narrative.isnot(None), Incident.probable_cause.isnot(None))
            )
            .order_by(Incident.ntsb_id)
        ).yield_per(batch_size)
        for incident, source_sha256 in incident_rows:
            record = NtsbIncidentRecord(
                ntsb_id=incident.ntsb_id,
                event_date=incident.event_date,
                event_city=incident.event_city,
                event_state=incident.event_state,
                event_country=incident.event_country,
                aircraft_make=incident.aircraft_make,
                aircraft_model=incident.aircraft_model,
                registration_number=incident.registration_number,
                fatal_injuries=incident.fatal_injuries,
                serious_injuries=incident.serious_injuries,
                minor_injuries=incident.minor_injuries,
                uninjured=incident.uninjured,
                weather_condition=incident.weather_condition,
                phase_of_flight=incident.phase_of_flight,
                probable_cause=incident.probable_cause,
                narrative=incident.narrative,
                source_url=incident.source_url,
            )
            documents = chunk_incident_narrative(
                record,
                source_run_id=incident.source_run_id,
                source_sha256=source_sha256,
            )
            if not check_only:
                delete_incident_narratives(incident.ntsb_id)
            for document in documents:
                expected_incidents[document.document_id] = str(incident.source_run_id)
                if not check_only:
                    incident_batch.append(document)
                if len(incident_batch) >= batch_size:
                    _flush_incidents(incident_batch)
                    incident_batch.clear()

        regulation_rows = db.execute(
            select(Regulation, SafetyIngestionRunRecord.source_sha256)
            .join(
                SafetyIngestionRunRecord,
                Regulation.source_run_id == SafetyIngestionRunRecord.run_id,
            )
            .where(Regulation.effective_date.isnot(None))
            .order_by(
                Regulation.cfr_title,
                Regulation.cfr_part,
                Regulation.cfr_section,
                Regulation.effective_date,
            )
        ).yield_per(batch_size)
        for regulation, source_sha256 in regulation_rows:
            record = EcfrSectionRecord(
                cfr_title=regulation.cfr_title,
                cfr_part=regulation.cfr_part,
                cfr_section=regulation.cfr_section,
                section_title=regulation.section_title,
                section_text=regulation.section_text,
                effective_date=regulation.effective_date,
                source_url=regulation.source_url,
            )
            document = regulation_document(
                record,
                source_run_id=regulation.source_run_id,
                source_sha256=source_sha256,
            )
            expected_regulations[document.document_id] = str(regulation.source_run_id)
            if not check_only:
                regulation_batch.append(document)
            if len(regulation_batch) >= batch_size:
                _flush_regulations(regulation_batch)
                regulation_batch.clear()

    if not check_only:
        _flush_incidents(incident_batch)
        _flush_regulations(regulation_batch)

    incident_report = compare_corpus_lineage(
        expected_incidents,
        indexed_lineage(get_incident_narratives_collection()),
    )
    regulation_report = compare_corpus_lineage(
        expected_regulations,
        indexed_lineage(get_faa_regulations_collection()),
    )
    consistent = (
        incident_report.consistent
        and regulation_report.consistent
        and not unversioned_incidents
        and not unversioned_regulations
    )
    return {
        "status": "passed" if consistent else "failed",
        "mode": "check_only" if check_only else "sync",
        "unversioned_sql_rows": {
            "incidents": unversioned_incidents or 0,
            "regulations": unversioned_regulations or 0,
        },
        "incident_narratives": asdict(incident_report) | {
            "consistent": incident_report.consistent
        },
        "faa_regulations": asdict(regulation_report) | {
            "consistent": regulation_report.consistent
        },
    }


def main() -> int:
    args = parse_args()
    payload = sync_corpus(check_only=args.check_only, batch_size=args.batch_size)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
