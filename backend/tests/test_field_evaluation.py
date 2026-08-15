"""Privacy, split, freeze, and reporting gates for physical field evaluation."""

import hashlib
import json
from pathlib import Path

import pytest

from evaluation.field.episodes import build_report
from evaluation.field.privacy import PrivacyViolation, verify_public_export
from evaluation.field.sanitizer import sanitize_capture
from scripts.evaluate_frozen_synthetic import evaluate


POLICY = Path(__file__).parents[1] / "integrity_core/policies/feeder-v1.json"


def line(second: int, aircraft: str = "A1B2C3", callsign: str = "PRIVATE1") -> str:
    return (
        f"MSG,3,1,42,{aircraft},42,2026/08/15,12:34:{second:02d}.000,"
        f"2026/08/15,12:34:{second:02d}.100,{callsign},12500,300,0,"
        f"39.{961200 + second:06d},-82.998800,0,2431,0,0,0,0"
    )


def test_sanitizer_enforces_relative_nonreversible_chronological_export(tmp_path: Path) -> None:
    captures = tmp_path / "private"
    captures.mkdir()
    entries = []
    for day in range(1, 8):
        source = captures / f"private-day-{day}.sbs"
        source.write_text("\n".join(line(value) for value in range(10, 16)) + "\n", encoding="utf-8")
        entries.append(
            {
                "day": day,
                "path": source.name,
                "usable": True,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            }
        )
    manifest = captures / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "known_private_values": ["A1B2C3", "PRIVATE1", "39.961210", "-82.998800"],
                "captures": entries,
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "public" / "features.jsonl"

    result = sanitize_capture(manifest, POLICY, output)
    rows = [json.loads(value) for value in output.read_text(encoding="utf-8").splitlines()]

    assert result["sessions"] == 7
    assert (output.with_suffix(".manifest.json")).exists()
    assert result["splits"] == ["development", "holdout", "validation"]
    assert {row["split"] for row in rows if row["public_session_id"] == rows[0]["public_session_id"]} == {"development"}
    assert rows[0]["elapsed_seconds"] == 0
    assert rows[0]["delta_east_nm"] == 0
    assert rows[0]["delta_north_nm"] == 0
    assert "A1B2C3" not in output.read_text(encoding="utf-8")
    assert "PRIVATE1" not in output.read_text(encoding="utf-8")
    assert verify_public_export(output, known_private_values=["A1B2C3", "PRIVATE1"]) == 42


@pytest.mark.parametrize(
    "payload,match",
    [
        ({"export_schema_version": "1.0", "icao_hex": "A1B2C3"}, "non-allow-listed"),
        ({"export_schema_version": "1.0", "public_track_id": "2026-08-15"}, "calendar date"),
        ({"export_schema_version": "1.0", "public_track_id": "/Users/private/capture"}, "path"),
    ],
)
def test_privacy_verifier_fails_closed(tmp_path: Path, payload: dict, match: str) -> None:
    artifact = tmp_path / "bad.jsonl"
    artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(PrivacyViolation, match=match):
        verify_public_export(artifact)


def test_report_refuses_policy_checksum_mismatch(tmp_path: Path) -> None:
    export = tmp_path / "features.jsonl"
    export.write_text("", encoding="utf-8")
    freeze = tmp_path / "freeze.json"
    freeze.write_text(json.dumps({"policy_sha256": "0" * 64}), encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        build_report(export, POLICY, freeze)


def test_missing_physical_holdout_is_reported_as_blocked_not_success(tmp_path: Path) -> None:
    export = tmp_path / "features.jsonl"
    export.write_text(
        json.dumps(
            {
                "split": "development",
                "public_track_id": "track_public",
                "elapsed_seconds": 0,
                "policy_state": "NOMINAL",
                "evidence_kinds": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    freeze = tmp_path / "freeze.json"
    freeze.write_text(
        json.dumps({"policy_sha256": hashlib.sha256(POLICY.read_bytes()).hexdigest()}),
        encoding="utf-8",
    )

    report = build_report(export, POLICY, freeze)

    assert report["status"] == "BLOCKED_CAPTURE_PENDING"
    assert report["gate"]["passed"] is False
    assert report["splits"]["holdout"]["reviewed_routine_traffic_integrity_alerts_per_track_hour"] is None


def test_frozen_policy_meets_synthetic_targeted_family_gate() -> None:
    result = evaluate(POLICY, cases=20)

    assert result["abrupt_targeted_recall"] >= 0.95
    assert result["gradual_targeted_recall"] >= 0.95
