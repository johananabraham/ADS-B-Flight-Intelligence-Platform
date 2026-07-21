"""Tests for source evidence extracted by the SBS ingestion service."""

from datetime import datetime, timezone

from services.ingestion.ingest import aircraft_state, merge_aircraft_state, parse_sbs_message


SBS_LINE = (
    "MSG,3,1,42,A1B2C3,42,2026/07/19,12:34:56.789,"
    "2026/07/19,12:34:56.800,DAL1842,12500,310,72,"
    "39.9612,-82.9988,800,2431,0,0,0,0"
)


def test_parser_preserves_source_time_and_stable_raw_identity() -> None:
    first = parse_sbs_message(SBS_LINE)
    retry = parse_sbs_message(SBS_LINE)

    assert first is not None
    assert retry is not None
    assert first["_observed_at"] == datetime(
        2026, 7, 19, 12, 34, 56, 789000, tzinfo=timezone.utc
    )
    assert first["_raw_message_id"] == retry["_raw_message_id"]
    assert len(first["_raw_message_id"]) == 64


def test_internal_evidence_fields_do_not_leak_into_mutable_track_state() -> None:
    aircraft_state.clear()
    parsed = parse_sbs_message(SBS_LINE)
    assert parsed is not None

    merged = merge_aircraft_state(parsed["hex"], parsed)

    assert "_observed_at" not in merged
    assert "_raw_message_id" not in merged
