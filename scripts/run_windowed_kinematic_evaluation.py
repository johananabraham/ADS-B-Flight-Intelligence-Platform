#!/usr/bin/env python3
"""Compare pairwise and short-window evidence on held-out synthetic sessions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.kinematic_harness import (
    DatasetSplit,
    ScenarioType,
    build_window_report,
    generate_dataset,
    validate_no_split_leakage,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--sessions", type=int, default=90)
    parser.add_argument("--split", choices=[item.value for item in DatasetSplit], default="test")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def check_report(report: dict[str, object]) -> None:
    metrics = report["metrics_by_scenario_type"]
    gradual = metrics[ScenarioType.GRADUAL_POSITION_DRIFT.value]
    clean = metrics[ScenarioType.CLEAN.value]
    if gradual["combined_detection_rate"] != 1.0:
        raise SystemExit("Window regression: gradual drift detection is not 100%")
    if clean["combined_detected"] != 0:
        raise SystemExit("Window regression: synthetic clean scenarios produced alerts")


def main() -> None:
    args = parse_args()
    scenarios = generate_dataset(seed=args.seed, session_count=args.sessions)
    validate_no_split_leakage(scenarios)
    report = build_window_report(scenarios, split=DatasetSplit(args.split))
    if args.check:
        check_report(report)
    rendered = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
