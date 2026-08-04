#!/usr/bin/env python3
"""Score a versioned observation dataset without making unsupported field claims."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.evaluation.calibration import (
    build_calibration_report,
    load_calibration_dataset,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest, observations = load_calibration_dataset(
        args.manifest, args.observations
    )
    report = build_calibration_report(manifest, observations)
    rendered = json.dumps(report, indent=2, default=str) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()
