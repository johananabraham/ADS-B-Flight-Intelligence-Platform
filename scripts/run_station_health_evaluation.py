#!/usr/bin/env python3
"""Run or enforce the deterministic edge-station health baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.evaluation.station_health_harness import (
    passes_offline_gate,
    run_station_health_evaluation,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--revision", default="working-tree")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    revision = args.revision
    if args.baseline and args.baseline.exists():
        revision = json.loads(args.baseline.read_text())["implementation_revision"]
    report = run_station_health_evaluation(implementation_revision=revision)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.check:
        if not passes_offline_gate(report):
            raise SystemExit("offline station-health gate failed")
        if args.baseline and report != json.loads(args.baseline.read_text()):
            raise SystemExit("offline station-health baseline drifted")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
