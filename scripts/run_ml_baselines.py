#!/usr/bin/env python3
"""Train and evaluate offline interpretable models on Generator 1.1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.kinematic_harness import generate_extended_dataset
from app.evaluation.ml_baselines import build_ml_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--sessions", type=int, default=90)
    parser.add_argument(
        "--implementation-revision",
        help="commit containing the evaluated implementation",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def compact_summary(report: dict[str, object]) -> dict[str, object]:
    model_fields = {
        name: {
            key: value
            for key, value in model.items()
            if key != "predictions"
        }
        for name, model in report["models"].items()
    }
    validation_fields = {
        name: {
            key: value
            for key, value in model.items()
            if key != "predictions"
        }
        for name, model in report["validation_models"].items()
    }
    return {
        key: value
        for key, value in report.items()
        if key not in {"models", "validation_models"}
    } | {
        "validation_models": validation_fields,
        "models": model_fields,
    }


def check_report(report: dict[str, object]) -> None:
    failures = []
    for split_name in ("validation_models", "models"):
        models = report[split_name]
        rules = models["rules_only"]
        for name in ("logistic_regression", "decision_tree", "random_forest"):
            result = models[name]
            if result["f1"] < rules["f1"]:
                failures.append(f"{split_name}.{name} F1 is below rules-only")
            if result["synthetic_control_sequence_alert_rate"] != 0:
                failures.append(f"{split_name}.{name} alerted on generated controls")
            if result["synthetic_impairment_sequence_alert_rate"] != 0:
                failures.append(f"{split_name}.{name} alerted on generated impairments")
            if result["field_false_alerts_per_flight_hour"] is not None:
                failures.append(f"{split_name}.{name} invented a field alert rate")
    if report["promotion_decision"] != "OFFLINE_EVALUATION_ONLY":
        failures.append("model promotion must remain offline-only")
    if failures:
        raise SystemExit("ML evaluation regression: " + "; ".join(failures))


def main() -> None:
    args = parse_args()
    reviewed = None
    if args.baseline:
        reviewed = json.loads(args.baseline.read_text(encoding="utf-8"))
    implementation_revision = args.implementation_revision
    if implementation_revision is None and reviewed is not None:
        implementation_revision = reviewed["implementation_revision"]
    if implementation_revision is None:
        raise SystemExit(
            "--implementation-revision is required when no reviewed baseline is supplied"
        )

    report = build_ml_report(
        generate_extended_dataset(seed=args.seed, session_count=args.sessions),
        seed=args.seed,
        implementation_revision=implementation_revision,
    )
    summary = compact_summary(report)
    if args.check:
        check_report(report)
    if reviewed is not None and reviewed != summary:
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
