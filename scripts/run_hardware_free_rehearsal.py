#!/usr/bin/env python3
"""Run deterministic integrity and receiver-health evidence without hardware."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.evaluation.station_health_harness import (
    passes_offline_gate,
    passes_receiver_recovery_gate,
    run_receiver_recovery_rehearsal,
    run_station_health_evaluation,
)
from scripts.evaluate_frozen_synthetic import evaluate


def build_rehearsal(
    *, policy_path: Path, cases: int, implementation_revision: str
) -> dict[str, object]:
    if not 1 <= cases <= 10_000:
        raise ValueError("cases must be between 1 and 10000")

    synthetic = evaluate(policy_path, cases)
    station_health = run_station_health_evaluation(
        implementation_revision=implementation_revision
    )
    receiver_recovery = run_receiver_recovery_rehearsal()
    checks = {
        "abrupt_targeted_recall_at_least_0_95": (
            synthetic["abrupt_targeted_recall"] >= 0.95
        ),
        "gradual_targeted_recall_at_least_0_95": (
            synthetic["gradual_targeted_recall"] >= 0.95
        ),
        "station_health_exact_match": passes_offline_gate(station_health),
        "receiver_recovery_sequence_match": passes_receiver_recovery_gate(
            receiver_recovery
        ),
    }
    return {
        "schema_version": "1.0",
        "evidence_class": "HARDWARE_FREE_REHEARSAL_ONLY",
        "status": "PASSED" if all(checks.values()) else "FAILED",
        "checks": checks,
        "components": {
            "frozen_policy_synthetic": synthetic,
            "station_health": station_health,
            "receiver_recovery": receiver_recovery,
        },
        "claim_boundaries": {
            "physical_sdr_messages": 0,
            "physical_esp32_sessions": 0,
            "live_mqtt_messages": 0,
            "field_calibration_claim_permitted": False,
            "measured_recovery_time_claim_permitted": False,
            "real_attack_detection_claim_permitted": False,
            "next_required_evidence": (
                "Use an authorized live receiver or consenting independent feeder "
                "for field calibration, then exercise the target ESP32 physically."
            ),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path("backend/integrity_core/policies/feeder-v1.json"),
    )
    parser.add_argument("--cases", type=int, default=20)
    parser.add_argument("--revision", default="working-tree")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    revision = args.revision
    if args.baseline and args.baseline.exists():
        revision = json.loads(args.baseline.read_text(encoding="utf-8"))["components"][
            "station_health"
        ]["implementation_revision"]

    try:
        report = build_rehearsal(
            policy_path=args.policy,
            cases=args.cases,
            implementation_revision=revision,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    if args.check:
        if report["status"] != "PASSED":
            raise SystemExit("hardware-free rehearsal gate failed")
        if args.baseline and report != json.loads(
            args.baseline.read_text(encoding="utf-8")
        ):
            raise SystemExit("hardware-free rehearsal baseline drifted")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
