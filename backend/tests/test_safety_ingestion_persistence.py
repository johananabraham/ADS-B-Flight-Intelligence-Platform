"""SQL and idempotency tests for safety-source persistence."""

import json
from datetime import date, datetime, timezone
from unittest.mock import Mock

from sqlalchemy.dialects import postgresql

from app.safety.ingestion import (
    SourceArtifact,
    SourceKind,
    ingestion_run_id,
    parse_ecfr_part_xml,
    parse_ntsb_carol_json,
    persist_ntsb_source,
)
from app.safety.ingestion.persistence import (
    build_incidents_upsert,
    build_regulations_upsert,
    build_run_insert,
)


NOW = datetime(2026, 8, 5, 3, tzinfo=timezone.utc)


def compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def parsed_ntsb():
    artifact = SourceArtifact(
        kind=SourceKind.NTSB_CAROL_JSON,
        source_uri="file:///exports/carol.json",
        retrieved_at=NOW,
        content=json.dumps(
            {
                "results": [
                    {
                        "ntsbNumber": "ERA26LA001",
                        "eventDate": "2026-07-01",
                        "probableCause": "Sample cause.",
                    }
                ]
            }
        ).encode(),
    )
    return parse_ntsb_carol_json(artifact)


def parsed_ecfr():
    artifact = SourceArtifact(
        kind=SourceKind.ECFR_PART_XML,
        source_uri="https://www.ecfr.gov/api/versioner/v1/full/date/title-14.xml?part=91",
        retrieved_at=NOW,
        effective_date=date(2026, 7, 24),
        parameters={"part": 91},
        content=(
            b'<DIV5 N="91" TYPE="PART"><DIV8 N="91.103" TYPE="SECTION">'
            b"<HEAD>Section 91.103</HEAD><P>Preflight action.</P></DIV8></DIV5>"
        ),
    )
    return parse_ecfr_part_xml(artifact)


def test_run_identity_and_manifest_insert_are_stable():
    parsed = parsed_ntsb()
    first = ingestion_run_id(parsed.report)
    retry = ingestion_run_id(parsed.report)

    assert first == retry
    sql = compiled(build_run_insert(parsed.report, ingested_at=NOW))
    assert "ON CONFLICT (source_kind, source_sha256, parser_version) DO NOTHING" in sql


def test_bulk_upserts_are_parameterized_and_use_correct_identities():
    ntsb = parsed_ntsb()
    run_id = ingestion_run_id(ntsb.report)
    incident_sql = compiled(build_incidents_upsert(ntsb.records, run_id))
    assert "ON CONFLICT (ntsb_id) DO UPDATE" in incident_sql
    assert "source_run_id" in incident_sql

    ecfr = parsed_ecfr()
    regulation_sql = compiled(build_regulations_upsert(ecfr.records, run_id))
    assert (
        "ON CONFLICT (cfr_title, cfr_part, cfr_section, effective_date) DO UPDATE"
        in regulation_sql
    )


def test_duplicate_manifest_skips_record_writes():
    parsed = parsed_ntsb()
    db = Mock()
    db.execute.return_value.scalar_one_or_none.return_value = None

    outcome = persist_ntsb_source(db, parsed, ingested_at=NOW)

    assert outcome.applied is False
    assert outcome.run_id == ingestion_run_id(parsed.report)
    assert db.execute.call_count == 1


def test_new_manifest_applies_records_in_same_transaction():
    parsed = parsed_ntsb()
    db = Mock()
    db.execute.return_value.scalar_one_or_none.return_value = ingestion_run_id(
        parsed.report
    )

    outcome = persist_ntsb_source(db, parsed, ingested_at=NOW)

    assert outcome.applied is True
    assert outcome.record_count == 1
    assert db.execute.call_count == 2
