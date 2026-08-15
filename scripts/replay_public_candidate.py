#!/usr/bin/env python3
"""Replay a frozen private selection through the shared integrity core."""

import argparse
import json
from datetime import datetime
from pathlib import Path

from evaluation.public_replay.replay import replay_candidate
from evaluation.public_replay.selection import CandidateSelection


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--license-approved", action="store_true")
    args = parser.parse_args()
    selected = json.loads(args.selection.read_text(encoding="utf-8"))
    trace = tuple(json.loads(line) for line in args.trace.read_text(encoding="utf-8").splitlines())
    selection = CandidateSelection(
        candidate_id=selected["candidate_id"],
        source_identifier=selected["source_identifier"],
        aircraft_identifier=selected["aircraft_identifier"],
        candidate_time=datetime.fromisoformat(selected["candidate_time"].replace("Z", "+00:00")),
        notam_identifier=selected["notam_identifier"],
        trace=trace,
    )
    result = replay_candidate(
        selection, args.policy, license_permits_processing=args.license_approved
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(result["outcome"])


if __name__ == "__main__":
    main()
