"""Deterministic selection, license, and all-outcome public replay tests."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from evaluation.public_replay.manifest import validate_sources
from evaluation.public_replay.replay import PublicOutcome, replay_candidate
from evaluation.public_replay.selection import (
    CandidateSelection,
    CandidateSelectionError,
    select_candidate,
)


POLICY = Path(__file__).parents[1] / "integrity_core/policies/feeder-v1.json"
START = datetime(2023, 6, 1, 12, 0, tzinfo=timezone.utc)
POLYGON = "POLYGON ((-1 -1, 1 -1, 1 1, -1 1, -1 -1))"


def candidate(identifier: str, offset: int = 0) -> dict:
    return {
        "id": identifier,
        "icao24": "a1b2c3",
        "time_of_spoofing": (START + timedelta(seconds=offset)).isoformat(),
        "WKT": "LINESTRING (0 0, 0.1 0.1)",
    }


def notam() -> dict:
    return {
        "notam_id": "NOTICE-1",
        "time_start": (START - timedelta(hours=1)).isoformat(),
        "time_end": (START + timedelta(hours=1)).isoformat(),
        "WKT": POLYGON,
    }


def trace(*, abrupt: bool = False) -> list[dict]:
    offsets = (-300, -240, -180, -120, -60, -1, 1, 60, 120, 180, 240, 300)
    rows = []
    for index, offset in enumerate(offsets):
        latitude = (offset - offsets[0]) * (300 / 3600 / 60)
        if abrupt and offset == 1:
            latitude += 0.1
        rows.append(
            {
                "observed_at": (START + timedelta(seconds=offset)).isoformat(),
                "latitude": latitude,
                "longitude": 0,
                "altitude_ft": 10_000,
                "ground_speed_knots": 300,
                "track_degrees": 0,
                "source_message_id": f"message-{index}",
            }
        )
    return rows


def selection(rows: list[dict]) -> CandidateSelection:
    return CandidateSelection(
        candidate_id="candidate_public_test",
        source_identifier="source-1",
        aircraft_identifier="A1B2C3",
        candidate_time=START,
        notam_identifier="NOTICE-1",
        trace=tuple(rows),
    )


def test_selection_is_before_scoring_and_stable_by_time_then_id() -> None:
    selected = select_candidate(
        [candidate("z-later", 1), candidate("b"), candidate("a")],
        [notam()],
        {"a1b2c3": trace()},
    )

    assert selected.source_identifier == "a"
    assert selected.candidate_time == START
    assert selected.candidate_id.startswith("candidate_")


def test_selection_requires_notam_overlap_and_six_reports_each_side() -> None:
    with pytest.raises(CandidateSelectionError):
        select_candidate([candidate("a")], [], {"a1b2c3": trace()})
    with pytest.raises(CandidateSelectionError):
        select_candidate(
            [candidate("a")], [notam()], {"a1b2c3": trace()[:10]}
        )


def test_replay_supports_detected_missed_insufficient_and_blocked_outcomes() -> None:
    detected = replay_candidate(selection(trace(abrupt=True)), POLICY, license_permits_processing=True)
    missed = replay_candidate(selection(trace()), POLICY, license_permits_processing=True)
    insufficient = replay_candidate(
        selection(trace()[:11]), POLICY, license_permits_processing=True
    )
    blocked = replay_candidate(selection(trace()), POLICY, license_permits_processing=False)

    assert detected["outcome"] == PublicOutcome.DETECTED.value
    assert missed["outcome"] == PublicOutcome.MISSED.value
    assert insufficient["outcome"] == PublicOutcome.INSUFFICIENT_DATA.value
    assert blocked["outcome"] == PublicOutcome.BLOCKED_REPLICATION.value
    for result in (detected, missed, insufficient, blocked):
        assert "confirmed spoofing" in result["claim_boundary"]


def test_source_manifest_license_and_checksums_fail_closed(tmp_path: Path) -> None:
    candidate_archive = tmp_path / "candidates.zip"
    notam_archive = tmp_path / "notams.zip"
    candidate_archive.write_bytes(b"candidate")
    notam_archive.write_bytes(b"notam")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "candidate_index": {
                    "filename": candidate_archive.name,
                    "md5": "wrong",
                    "license_status": "REVIEW_REQUIRED",
                },
                "notam_index": {
                    "filename": notam_archive.name,
                    "md5": "wrong",
                    "license_status": "REVIEW_REQUIRED",
                },
                "surrounding_trace": {"processing_status": "BLOCKED"},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="license"):
        validate_sources(manifest, candidate_archive, notam_archive)


def test_checked_in_result_is_an_honest_block_not_a_synthetic_substitute() -> None:
    result_path = Path(__file__).parents[2] / "evaluation/results/public-anomaly-candidate-v1.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))

    assert result["outcome"] == "BLOCKED_REPLICATION"
    assert "license" in result["reason"]
    assert "confirmed spoofing" in result["claim_boundary"]
