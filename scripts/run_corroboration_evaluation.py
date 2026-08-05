#!/usr/bin/env python3
"""Run or enforce the deterministic offline corroboration baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.evaluation.corroboration_harness import (
    passes_offline_gate,
    run_corroboration_evaluation,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hours", type=int, default=4)
    parser.add_argument("--interval-seconds", type=int, default=20)
    parser.add_argument("--revision", default="working-tree")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    revision = args.revision
    if args.baseline and args.baseline.exists():
        revision = json.loads(args.baseline.read_text())["implementation_revision"]
    report = run_corroboration_evaluation(
        hours=args.hours,
        interval_seconds=args.interval_seconds,
        implementation_revision=revision,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if args.check:
        if not passes_offline_gate(report):
            raise SystemExit("offline corroboration gate failed")
        if args.baseline and report != json.loads(args.baseline.read_text()):
            raise SystemExit("offline corroboration baseline drifted")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
