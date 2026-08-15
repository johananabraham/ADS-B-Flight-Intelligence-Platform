#!/usr/bin/env python3
"""Evaluate abrupt and gradual targeted families with one frozen live policy."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.schemas.observation import ObservationProvenance, ObservationSourceType, TrackObservation
from integrity_core import EvidenceKind, IntegrityEngine, load_policy


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def item(case: int, index: int, latitude: float, longitude: float) -> TrackObservation:
    timestamp = START + timedelta(days=case, seconds=index)
    return TrackObservation(
        observation_id=uuid5(NAMESPACE_URL, f"frozen-synthetic:{case}:{index}"),
        provenance=ObservationProvenance(
            source_type=ObservationSourceType.SIMULATION,
            source_id=f"frozen-family-{case}",
        ),
        icao_hex=f"A{case:05X}",
        observed_at=timestamp,
        received_at=timestamp,
        latitude=latitude,
        longitude=longitude,
        altitude_ft=10_000,
        ground_speed_knots=300,
        track_degrees=0,
        raw_message_id=f"synthetic-{case}-{index}",
    )


def evaluate(policy_path: Path, cases: int = 20) -> dict:
    policy = load_policy(policy_path)
    abrupt_detected = gradual_detected = 0
    for case in range(cases):
        abrupt = IntegrityEngine(policy)
        abrupt.ingest(item(case, 0, 0, 0))
        snapshot, _ = abrupt.ingest(item(case, 1, 0.02 + case * 0.0001, 0))
        if EvidenceKind.PAIR_KINEMATIC in {value.kind for value in snapshot.active_evidence}:
            abrupt_detected += 1

        gradual = IntegrityEngine(policy)
        for index in range(6):
            snapshot, _ = gradual.ingest(
                item(
                    case + cases,
                    index,
                    index * (300 / 3600 / 60),
                    index * (0.00002 + case * 0.0000002),
                )
            )
        if EvidenceKind.WINDOW_KINEMATIC in {value.kind for value in snapshot.active_evidence}:
            gradual_detected += 1
    return {
        "schema_version": "1.0",
        "policy_sha256": hashlib.sha256(policy_path.read_bytes()).hexdigest(),
        "cases_per_family": cases,
        "abrupt_detected": abrupt_detected,
        "abrupt_targeted_recall": abrupt_detected / cases,
        "gradual_detected": gradual_detected,
        "gradual_targeted_recall": gradual_detected / cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.cases <= 10_000:
        parser.error("cases must be between 1 and 10000")
    result = evaluate(args.policy, args.cases)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    if result["abrupt_targeted_recall"] < 0.95 or result["gradual_targeted_recall"] < 0.95:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
