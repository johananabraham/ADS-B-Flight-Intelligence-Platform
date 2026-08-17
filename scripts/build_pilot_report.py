#!/usr/bin/env python3
"""Build deterministic JSON and Markdown reports from sanitized pilot bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.pilot import (
    build_pilot_report,
    load_participant_evidence,
    render_pilot_report_markdown,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path, required=True)
    parser.add_argument("--json-output", type=Path, required=True)
    parser.add_argument("--markdown-output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    existing = [
        path for path in (args.json_output, args.markdown_output) if path.exists()
    ]
    if existing and not args.force:
        raise SystemExit(f"refusing to overwrite existing output: {existing[0]}")
    participants = tuple(load_participant_evidence(path) for path in args.input)
    report = build_pilot_report(participants)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.markdown_output.write_text(
        render_pilot_report_markdown(report),
        encoding="utf-8",
    )
    print(report["status"])
    if report["status"] != "PILOT_SUCCESS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
