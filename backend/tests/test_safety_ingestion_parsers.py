"""Fixture-backed safety-source parser and lineage tests."""

import json
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from app.safety.ingestion import (
    SourceArtifact,
    SourceKind,
    parse_ecfr_part_xml,
    parse_ntsb_carol_json,
)


RETRIEVED_AT = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)


def ntsb_artifact(payload: object) -> SourceArtifact:
    return SourceArtifact(
        kind=SourceKind.NTSB_CAROL_JSON,
        source_uri="https://data.ntsb.gov/carol-main-public/query-entry",
        retrieved_at=RETRIEVED_AT,
        content=json.dumps(payload).encode(),
    )


def ecfr_artifact(xml: str) -> SourceArtifact:
    return SourceArtifact(
        kind=SourceKind.ECFR_PART_XML,
        source_uri=(
            "https://www.ecfr.gov/api/versioner/v1/full/2026-07-24/"
            "title-14.xml?part=91"
        ),
        retrieved_at=RETRIEVED_AT,
        effective_date=date(2026, 7, 24),
        parameters={"part": 91},
        content=xml.encode(),
    )


def test_carol_parser_preserves_lineage_and_reports_quality():
    payload = {
        "results": [
            {
                "ntsbNumber": "ERA26LA001",
                "eventDate": "2026-07-01T00:00:00Z",
                "eventCity": "Sample City",
                "eventStateOrRegion": "FL",
                "eventCountry": "United States",
                "aircraft": [
                    {"make": "Cessna", "model": "172S", "registration": "N123AB"}
                ],
                "fatalInjuryCount": 0,
                "seriousInjuryCount": 1,
                "weatherCondition": "VMC",
                "broadPhaseOfFlight": "Landing",
                "probableCause": "The pilot's loss of directional control.",
                "investigationUrl": "https://www.ntsb.gov/investigations/ERA26LA001",
            },
            {"ntsbNumber": "ERA26LA001", "eventDate": "2026-07-01"},
            {"ntsbNumber": "ERA26LA002", "eventDate": "not-a-date"},
        ]
    }

    result = parse_ntsb_carol_json(ntsb_artifact(payload))

    assert len(result.records) == 1
    assert result.records[0].ntsb_id == "ERA26LA001"
    assert result.records[0].aircraft_model == "172S"
    assert result.report.source_record_count == 3
    assert result.report.parsed_record_count == 1
    assert result.report.duplicate_identifier_count == 1
    assert result.report.rejected_record_count == 1
    assert {issue.code for issue in result.report.issues} == {
        "DUPLICATE_IDENTIFIER",
        "INVALID_RECORD",
    }
    assert len(result.report.source_sha256) == 64


def test_carol_parser_accepts_utf8_bom_and_array_root():
    content = b"\xef\xbb\xbf" + json.dumps(
        [{"ntsbNumber": "CEN26FA002", "eventDate": "07/04/2026"}]
    ).encode()
    artifact = SourceArtifact(
        kind=SourceKind.NTSB_CAROL_JSON,
        source_uri="file:///private/export.json",
        retrieved_at=RETRIEVED_AT,
        content=content,
    )

    result = parse_ntsb_carol_json(artifact)

    assert result.records[0].event_date == date(2026, 7, 4)


def test_ecfr_parser_keeps_sections_whole_and_dated():
    xml = """<?xml version="1.0"?>
    <DIV5 N="91" TYPE="PART">
      <DIV8 N="91.103" TYPE="SECTION">
        <HEAD>§ 91.103 Preflight action.</HEAD>
        <P>Each pilot in command shall, before beginning a flight, become familiar
        with all available information concerning that flight.</P>
      </DIV8>
      <DIV8 N="91.155" TYPE="SECTION">
        <HEAD>§ 91.155 Basic VFR weather minimums.</HEAD>
        <P>No person may operate an aircraft under VFR when visibility is less than
        the prescribed minimum.</P>
      </DIV8>
    </DIV5>"""

    result = parse_ecfr_part_xml(ecfr_artifact(xml))

    assert [record.cfr_section for record in result.records] == ["91.103", "91.155"]
    assert "all available information" in result.records[0].section_text
    assert result.records[0].effective_date == date(2026, 7, 24)
    assert result.records[0].source_url.endswith("/title-14/section-91.103")
    assert result.report.parsed_record_count == 2
    assert result.report.rejected_record_count == 0


def test_ecfr_parser_rejects_wrong_kind_and_missing_effective_date():
    artifact = ntsb_artifact([])
    with pytest.raises(ValueError, match="ECFR_PART_XML"):
        parse_ecfr_part_xml(artifact)

    with pytest.raises(ValidationError, match="retrieved_at"):
        SourceArtifact(
            kind=SourceKind.ECFR_PART_XML,
            source_uri="https://www.ecfr.gov/api/versioner/v1/full/date/title-14.xml",
            retrieved_at=datetime(2026, 8, 4, 12),
            content=b"<DIV5 />",
            parameters={"part": 91},
        )
