#!/usr/bin/env python3
"""Wrap reviewed daily sidecar summaries in a strict pilot evidence bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evaluation.pilot.report import (
    DailySnapshot,
    KeepInstalled,
    OutcomeCode,
    ParticipantEvidence,
    PilotSummary,
    ReadinessStatus,
    UsefulOutcome,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--participant-id", required=True)
    parser.add_argument("--summary", action="append", type=Path, default=[])
    parser.add_argument("--installation-minutes", type=int)
    parser.add_argument("--installation-not-attempted", action="store_true")
    parser.add_argument("--assisted-installation", action="store_true")
    parser.add_argument("--readiness-status", choices=("READY", "NOT_READY"), required=True)
    parser.add_argument("--state-meanings-explained-correctly", action="store_true")
    parser.add_argument("--drops-investigated", action="store_true")
    parser.add_argument(
        "--useful-outcome",
        choices=("OPERATIONAL_FINDING", "USABILITY_CHANGE", "NONE"),
        required=True,
    )
    parser.add_argument("--keep-installed", choices=("YES", "NO", "UNSURE"), required=True)
    parser.add_argument(
        "--outcome-code",
        action="append",
        default=[],
        choices=(
            "INSTALLABILITY",
            "RELIABILITY",
            "COMPREHENSION",
            "OPERATIONAL_FINDING",
            "NO_OBSERVED_VALUE",
            "PRIVACY_CONCERN",
            "FEATURE_REQUEST",
        ),
    )
    parser.add_argument("--withdrawn", action="store_true")
    parser.add_argument("--confirm-consent", action="store_true")
    parser.add_argument("--confirm-privacy-review", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists() and not args.force:
        raise SystemExit(f"refusing to overwrite existing output: {args.output}")
    snapshots = []
    for day_index, path in enumerate(args.summary, start=1):
        text = path.read_text(encoding="utf-8")
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("daily pilot summary must be a JSON object")
        snapshots.append(
            DailySnapshot(
                day_index=day_index,
                summary=PilotSummary.model_validate_json(text),
            )
        )
    bundle = ParticipantEvidence(
        participant_id=args.participant_id,
        consent_confirmed=args.confirm_consent,
        privacy_review_confirmed=args.confirm_privacy_review,
        withdrawn=args.withdrawn,
        installation_attempted=not args.installation_not_attempted,
        unaided_installation=(
            not args.assisted_installation and not args.installation_not_attempted
        ),
        installation_minutes_rounded=args.installation_minutes,
        readiness_status=ReadinessStatus(args.readiness_status),
        daily_snapshots=tuple(snapshots),
        state_meanings_explained_correctly=(
            args.state_meanings_explained_correctly
        ),
        drops_investigated=args.drops_investigated,
        useful_outcome=UsefulOutcome(args.useful_outcome),
        keep_installed=KeepInstalled(args.keep_installed),
        outcome_codes=tuple(OutcomeCode(code) for code in args.outcome_code),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        bundle.model_dump_json(indent=2) + "\n",
        encoding="utf-8",
    )
    print("VALIDATED")


if __name__ == "__main__":
    main()
