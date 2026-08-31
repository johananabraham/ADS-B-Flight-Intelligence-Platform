"""Hardware-free evidence rehearsal contract tests."""

from pathlib import Path
from typing import cast

import pytest

from backend.app.evaluation.station_health_harness import (
    run_receiver_recovery_rehearsal,
)
from scripts.run_hardware_free_rehearsal import build_rehearsal


POLICY = Path("backend/integrity_core/policies/feeder-v1.json")


def test_receiver_recovery_rehearsal_matches_expected_policy_sequence() -> None:
    report = run_receiver_recovery_rehearsal()
    timeline = cast(list[dict[str, object]], report["timeline"])
    boundaries = cast(dict[str, object], report["verification_boundaries"])

    assert report["exact_sequence_match"] is True
    assert [item["actual_state"] for item in timeline] == [
        "HEALTHY",
        "DEGRADED",
        "STALE",
        "HEALTHY",
    ]
    assert boundaries == {
        "physical_receiver_disconnects": 0,
        "physical_esp32_sessions": 0,
        "measured_recovery_time_permitted": False,
        "field_reliability_claim_permitted": False,
    }


def test_aggregate_rehearsal_passes_without_granting_field_claims() -> None:
    report = build_rehearsal(
        policy_path=POLICY,
        cases=2,
        implementation_revision="test-revision",
    )
    checks = cast(dict[str, bool], report["checks"])
    boundaries = cast(dict[str, object], report["claim_boundaries"])

    assert report["status"] == "PASSED"
    assert all(checks.values())
    assert boundaries["physical_sdr_messages"] == 0
    assert boundaries["field_calibration_claim_permitted"] is False
    assert boundaries["real_attack_detection_claim_permitted"] is False


@pytest.mark.parametrize("cases", [0, 10_001])
def test_aggregate_rehearsal_rejects_unbounded_case_counts(cases: int) -> None:
    with pytest.raises(ValueError, match="cases must be between 1 and 10000"):
        build_rehearsal(
            policy_path=POLICY,
            cases=cases,
            implementation_revision="test-revision",
        )
