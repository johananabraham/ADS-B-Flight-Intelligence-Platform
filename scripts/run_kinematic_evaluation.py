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


def main() -> None:
    args = parse_args()
    scenarios = generate_dataset(seed=args.seed, session_count=args.sessions)
    validate_no_split_leakage(scenarios)
    report = build_report(scenarios, split=DatasetSplit(args.split))
    if args.check:
        check_baseline(report)
    rendered = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
