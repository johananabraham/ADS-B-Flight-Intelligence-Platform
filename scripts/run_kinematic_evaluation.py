#!/usr/bin/env python3
"""Generate and score the held-out deterministic kinematic scenario suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.kinematic_harness import (
    DatasetSplit,
    ScenarioType,
    build_report,
    generate_dataset,
    validate_no_split_leakage,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--sessions", type=int, default=90)
    parser.add_argument("--split", choices=[value.value for value in DatasetSplit], default="test")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path, help="compare live metrics to a reviewed result")
    parser.add_argument("--check", action="store_true", help="enforce rules-only baseline gates")
    return parser.parse_args()


def check_baseline(report: dict[str, object]) -> None:
    metrics = report["metrics_by_scenario_type"]
    assert isinstance(metrics, dict)
    required_detection = (
        ScenarioType.ABRUPT_POSITION,
        ScenarioType.ABRUPT_ALTITUDE,
        ScenarioType.ABRUPT_VELOCITY,
        ScenarioType.ABRUPT_HEADING,
    )
    failures = []
    if report["synthetic_clean_sequence_alert_rate"] != 0:
        failures.append("synthetic clean scenarios produced alerts")
    for scenario_type in required_detection:
        result = metrics[scenario_type.value]
        if result["detection_rate"] != 1.0:
            failures.append(f"{scenario_type.value} detection_rate is not 1.0")
    if failures:
        raise SystemExit("Evaluation regression: " + "; ".join(failures))


def compare_reviewed_baseline(
    report: dict[str, object],
    baseline_path: Path,
    *,
    seed: int,
    sessions: int,
    split_counts: dict[str, int],
) -> None:
    reviewed = json.loads(baseline_path.read_text(encoding="utf-8"))
    expected = {
        "generator": {
            "version": report["generator"]["version"],
            "root_seed": seed,
            "source_sessions": sessions,
            "split_source_sessions": split_counts,
        },
        "policy_version": report["policy_version"],
        "evaluated_split": report["evaluated_split"],
        "scenario_count": report["scenario_count"],
        "pair_count": report["pair_count"],
        "synthetic_clean_sequence_alert_rate": report[
            "synthetic_clean_sequence_alert_rate"
        ],
        "attack_detection_rate": report["attack_detection_rate"],
        "metrics_by_scenario_type": report["metrics_by_scenario_type"],
    }
    actual = {
        "generator": {
            "version": reviewed["generator"]["version"],
            "root_seed": reviewed["generator"]["root_seed"],
            "source_sessions": reviewed["generator"]["source_sessions"],
            "split_source_sessions": reviewed["generator"]["split_source_sessions"],
        },
        **{key: reviewed[key] for key in expected if key != "generator"},
    }
    if actual != expected:
        raise SystemExit(
            "Reviewed baseline does not match live output; regenerate and review it."
        )


def main() -> None:
    args = parse_args()
    scenarios = generate_dataset(seed=args.seed, session_count=args.sessions)
    validate_no_split_leakage(scenarios)
    report = build_report(scenarios, split=DatasetSplit(args.split))
    split_counts = {
        split.value: len(
            {
                scenario.source_session_id
                for scenario in scenarios
                if scenario.split is split
            }
        )
        for split in DatasetSplit
    }
    if args.check:
        check_baseline(report)
    if args.baseline:
        compare_reviewed_baseline(
            report,
            args.baseline,
            seed=args.seed,
            sessions=args.sessions,
            split_counts=split_counts,
        )
    rendered = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
