#!/usr/bin/env python3
"""Prove safety-source persistence and idempotency against PostgreSQL."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models import (
    Incident,
    Regulation,
    SafetyIngestionRejectionRecord,
    SafetyIngestionRunRecord,
)
from app.safety.ingestion import (
    SourceArtifact,
    SourceKind,
    parse_ecfr_part_xml,
    parse_ntsb_carol_json,
    persist_ecfr_source,
    persist_ntsb_source,
)


NOW = datetime(2026, 8, 5, 3, tzinfo=timezone.utc)


def _sources():
    ntsb = parse_ntsb_carol_json(
        SourceArtifact(
            kind=SourceKind.NTSB_CAROL_JSON,
            source_uri="fixture://ci/ntsb-carol.json",
            retrieved_at=NOW,
            content=json.dumps(
                {
                    "results": [
                        {
                            "ntsbNumber": "TEST26LA001",
                            "eventDate": "2026-07-01",
                            "probableCause": "Synthetic ingestion verification only.",
                        },
                        {"ntsbNumber": "TEST26LA001", "eventDate": "2026-07-01"},
                    ]
                }
            ).encode(),
        )
    )
    ecfr = parse_ecfr_part_xml(
        SourceArtifact(
            kind=SourceKind.ECFR_PART_XML,
            source_uri="fixture://ci/ecfr-part-999.xml",
            retrieved_at=NOW,
            effective_date=date(1900, 1, 1),
            parameters={"part": 999},
            content=(
                b'<DIV5 N="999" TYPE="PART">'
                b'<DIV8 N="999.9999" TYPE="SECTION">'
                b"<HEAD>Verification fixture.</HEAD><P>Not regulatory text.</P>"
                b"</DIV8></DIV5>"
            ),
        )
    )
    return ntsb, ecfr


def verify() -> dict[str, object]:
    ntsb, ecfr = _sources()
    db = SessionLocal()
    try:
        first_ntsb = persist_ntsb_source(db, ntsb, ingested_at=NOW)
        retry_ntsb = persist_ntsb_source(db, ntsb, ingested_at=NOW)
        first_ecfr = persist_ecfr_source(db, ecfr, ingested_at=NOW)
        retry_ecfr = persist_ecfr_source(db, ecfr, ingested_at=NOW)
        db.flush()

        run_ids = (first_ntsb.run_id, first_ecfr.run_id)
        run_count = db.scalar(
            select(func.count()).select_from(SafetyIngestionRunRecord).where(
                SafetyIngestionRunRecord.run_id.in_(run_ids)
            )
        )
        rejection_count = db.scalar(
            select(func.count()).select_from(SafetyIngestionRejectionRecord).where(
                SafetyIngestionRejectionRecord.run_id == first_ntsb.run_id
            )
        )
        incident_count = db.scalar(
            select(func.count()).select_from(Incident).where(
                Incident.ntsb_id == "TEST26LA001"
            )
        )
        regulation_count = db.scalar(
            select(func.count()).select_from(Regulation).where(
                Regulation.cfr_part == 999,
                Regulation.cfr_section == "999.9999",
                Regulation.effective_date == date(1900, 1, 1),
            )
        )
        if (run_count, rejection_count, incident_count, regulation_count) != (2, 1, 1, 1):
            raise RuntimeError(
                "unexpected row counts: "
                f"{run_count}/{rejection_count}/{incident_count}/{regulation_count}"
            )
        if not first_ntsb.applied or retry_ntsb.applied:
            raise RuntimeError("NTSB source retry was not idempotent")
        if not first_ecfr.applied or retry_ecfr.applied:
            raise RuntimeError("eCFR source retry was not idempotent")
        return {
            "status": "passed",
            "source_runs": run_count,
            "dead_letters": rejection_count,
            "incidents": incident_count,
            "regulations": regulation_count,
            "retries_applied": 0,
        }
    finally:
        db.rollback()
        db.close()


def main() -> int:
    try:
        result = verify()
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
