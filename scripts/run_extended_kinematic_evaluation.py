#!/usr/bin/env python3
"""Generate and score the held-out Generator 1.1 scenario suite."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.kinematic_harness import (
    DatasetSplit,
    KinematicScenario,
    ScenarioClass,
    ScenarioType,
    build_extended_report,
    generate_extended_dataset,
    validate_no_split_leakage,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--sessions", type=int, default=90)
    parser.add_argument(
        "--split",
        choices=[value.value for value in DatasetSplit],
        default=DatasetSplit.TEST.value,
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--summary-output",
        type=Path,
        help="write the compact reviewable baseline fields",
    )
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def split_counts(scenarios: tuple[KinematicScenario, ...]) -> dict[str, int]:
    return {
        split.value: len(
            {
                scenario.source_session_id
                for scenario in scenarios
                if scenario.split is split
            }
        )
        for split in DatasetSplit
    }


def reviewed_summary(
    report: dict[str, object],
    *,
    seed: int,
    sessions: int,
    source_split_counts: dict[str, int],
) -> dict[str, object]:
    generator = report["generator"]
    return {
        "report_schema_version": report["report_schema_version"],
        "scope": report["scope"],
        "generator": {
            "version": generator["version"],
            "root_seed": seed,
            "source_sessions": sessions,
            "variants_per_session": len(ScenarioType),
            "split_source_sessions": source_split_counts,
        },
        "policy_version": report["policy_version"],
        "evaluated_split": report["evaluated_split"],
        "scenario_count": report["scenario_count"],
        "pair_count": report["pair_count"],
        "synthetic_control_sequence_alert_rate": report[
            "synthetic_control_sequence_alert_rate"
        ],
        "synthetic_impairment_sequence_alert_rate": report[
            "synthetic_impairment_sequence_alert_rate"
        ],
        "attack_detection_rate": report["attack_detection_rate"],
        "metrics_by_scenario_class": report["metrics_by_scenario_class"],
        "metrics_by_scenario_type": report["metrics_by_scenario_type"],
        "limitations": report["limitations"],
    }


def check_report(report: dict[str, object]) -> None:
    failures = []
    if report["synthetic_control_sequence_alert_rate"] != 0:
        failures.append("synthetic controls produced kinematic alerts")
    if report["synthetic_impairment_sequence_alert_rate"] != 0:
        failures.append("timing impairments produced kinematic alerts")
    metrics = report["metrics_by_scenario_type"]
    for scenario_type in (
        ScenarioType.ABRUPT_POSITION,
        ScenarioType.ABRUPT_ALTITUDE,
        ScenarioType.ABRUPT_VELOCITY,
        ScenarioType.ABRUPT_HEADING,
    ):
        if metrics[scenario_type.value]["detection_rate"] != 1:
            failures.append(f"{scenario_type.value} detection_rate is not 1.0")
    class_metrics = report["metrics_by_scenario_class"]
    if class_metrics[ScenarioClass.CONTROL.value]["scenarios"] == 0:
        failures.append("no control scenarios were evaluated")
    if failures:
        raise SystemExit("Evaluation regression: " + "; ".join(failures))


def main() -> None:
    args = parse_args()
    scenarios = generate_extended_dataset(seed=args.seed, session_count=args.sessions)
    validate_no_split_leakage(scenarios)
    report = build_extended_report(scenarios, split=DatasetSplit(args.split))
    summary = reviewed_summary(
        report,
        seed=args.seed,
        sessions=args.sessions,
        source_split_counts=split_counts(scenarios),
    )
    if args.check:
        check_report(report)
    if args.baseline:
        reviewed = json.loads(args.baseline.read_text(encoding="utf-8"))
        if reviewed != summary:
            raise SystemExit(
                "Reviewed baseline does not match live output; regenerate and review it."
            )
    rendered = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.summary_output:
        args.summary_output.parent.mkdir(parents=True, exist_ok=True)
        args.summary_output.write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
    print(rendered, end="")


if __name__ == "__main__":
    main()
