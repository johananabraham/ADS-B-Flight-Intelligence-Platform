"""Versioned ingestion status and unified CLI tests."""

import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from app.safety.ingestion import cli, status


def test_status_reports_latest_manifests_database_and_vector_counts(monkeypatch):
    run = SimpleNamespace(
        run_id=UUID("11111111-1111-1111-1111-111111111111"),
        source_kind="NTSB_CAROL_JSON",
        source_uri="fixture://ntsb.json",
        source_sha256="a" * 64,
        source_bytes=100,
        retrieved_at=datetime(2026, 8, 10, tzinfo=timezone.utc),
        effective_date=date(2026, 8, 9),
        parser_version="1.0",
        source_record_count=10,
        parsed_record_count=9,
        rejected_record_count=1,
        duplicate_identifier_count=0,
    )
    db = Mock()
    db.__enter__ = Mock(return_value=db)
    db.__exit__ = Mock(return_value=False)
    db.scalars.side_effect = [
        Mock(first=Mock(return_value=run)),
        Mock(first=Mock(return_value=None)),
    ]
    db.scalar.side_effect = [1, 1, 9, 0]
    monkeypatch.setattr(status, "SessionLocal", Mock(return_value=db))
    monkeypatch.setattr(
        status,
        "get_collection_stats",
        Mock(return_value={"incident_narratives": 9, "faa_regulations": 0}),
    )

    result = status.get_ingestion_status()

    assert result["database"] == {
        "source_runs": 1,
        "rejections": 1,
        "incidents": 9,
        "regulations": 0,
    }
    assert result["latest_manifests"]["NTSB_CAROL_JSON"]["run_id"] == str(
        run.run_id
    )
    assert result["vectorstore"]["incident_narratives"] == 9


def test_cli_status_does_not_require_report(monkeypatch, capsys):
    monkeypatch.setattr(
        cli,
        "get_ingestion_status",
        Mock(return_value={"database": {"incidents": 3}}),
    )

    assert cli.main(["status"]) == 0
    assert json.loads(capsys.readouterr().out)["database"]["incidents"] == 3


def test_cli_requires_report_for_ingestion(tmp_path):
    source = tmp_path / "ntsb.json"
    source.write_text('{"results": []}')

    with pytest.raises(SystemExit, match="--report is required"):
        cli.main(["--validate-only", "ntsb-json", "--input", str(source)])


def test_cli_validate_only_writes_report_without_database(tmp_path):
    source = tmp_path / "ntsb.json"
    report = tmp_path / "report.json"
    source.write_text(
        json.dumps(
            {
                "results": [
                    {
                        "ntsbNumber": "TEST26LA020",
                        "eventDate": "2026-08-01",
                        "probableCause": "Synthetic CLI validation only.",
                    }
                ]
            }
        )
    )

    result = cli.main(
        [
            "--report",
            str(report),
            "--validate-only",
            "ntsb-json",
            "--input",
            str(source),
        ]
    )

    payload = json.loads(report.read_text())
    assert result == 0
    assert payload["validation"]["parsed_record_count"] == 1
    assert "database" not in payload
