#!/usr/bin/env python3
"""Build the deterministic reviewed routine-traffic integrity report."""

import argparse
import json
from pathlib import Path

from evaluation.field.episodes import build_report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--freeze-manifest", type=Path, required=True)
    parser.add_argument("--reviews", type=Path)
    parser.add_argument("--synthetic-results", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(
        args.export,
        args.policy,
        args.freeze_manifest,
        reviews_path=args.reviews,
        synthetic_results_path=args.synthetic_results,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(report["status"])
    if report["status"] == "GATE_NOT_MET":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
