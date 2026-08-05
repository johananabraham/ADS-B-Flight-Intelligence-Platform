#!/usr/bin/env python3
"""Compare pairwise and short-window evidence on held-out synthetic sessions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.kinematic_harness import (
    DatasetSplit,
    GENERATOR_VERSION,
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
    parser.add_argument("--baseline", type=Path, help="compare metrics to a reviewed result")
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


def reviewed_result(
    report: dict[str, object],
    *,
    seed: int,
    sessions: int,
    split_counts: dict[str, int],
) -> dict[str, object]:
    return {
        "report_schema_version": report["report_schema_version"],
        "scope": report["scope"],
        "generator": {
            "version": GENERATOR_VERSION,
            "root_seed": seed,
            "source_sessions": sessions,
            "split_source_sessions": split_counts,
        },
        "evaluated_split": report["evaluated_split"],
        "scenario_count": report["scenario_count"],
        "pair_policy_version": report["pair_policy_version"],
        "window_policy": report["window_policy"],
        "metrics_by_scenario_type": report["metrics_by_scenario_type"],
        "limitations": report["limitations"],
    }


def compare_reviewed_baseline(result: dict[str, object], baseline_path: Path) -> None:
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    comparable = {key: baseline[key] for key in result}
    if comparable != result:
        raise SystemExit(
            "Reviewed window baseline does not match live output; regenerate and review it."
        )


def main() -> None:
    args = parse_args()
    scenarios = generate_dataset(seed=args.seed, session_count=args.sessions)
    validate_no_split_leakage(scenarios)
    report = build_window_report(scenarios, split=DatasetSplit(args.split))
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
    result = reviewed_result(
        report,
        seed=args.seed,
        sessions=args.sessions,
        split_counts=split_counts,
    )
    if args.check:
        check_report(report)
    if args.baseline:
        compare_reviewed_baseline(result, args.baseline)
    rendered = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
