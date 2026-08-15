"""Replay a preselected public candidate through the frozen integrity core."""

from __future__ import annotations

import hashlib
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.schemas.observation import ObservationProvenance, ObservationSourceType, TrackObservation
from integrity_core import EvidenceKind, IntegrityEngine, load_policy

from .selection import CandidateSelection, _time


class PublicOutcome(str, Enum):
    DETECTED = "DETECTED"
    MISSED = "MISSED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BLOCKED_REPLICATION = "BLOCKED_REPLICATION"


RELEVANT_KINDS = {EvidenceKind.PAIR_KINEMATIC, EvidenceKind.WINDOW_KINEMATIC}


def blocked_result(reason: str, policy_path: str | Path) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "outcome": PublicOutcome.BLOCKED_REPLICATION.value,
        "description": "Public research GPS-anomaly candidate replication",
        "reason": reason,
        "policy_sha256": hashlib.sha256(Path(policy_path).read_bytes()).hexdigest(),
        "claim_boundary": "This is not evidence of confirmed spoofing or malicious activity.",
    }


def replay_candidate(
    selection: CandidateSelection,
    policy_path: str | Path,
    *,
    license_permits_processing: bool,
) -> dict[str, Any]:
    if not license_permits_processing:
        return blocked_result("Source licensing has not been approved for processing.", policy_path)
    policy = load_policy(policy_path)
    engine = IntegrityEngine(policy)
    relevant = []
    usable = 0
    for index, item in enumerate(selection.trace):
        try:
            observed_at = _time(item["observed_at"])
            observation = TrackObservation(
                observation_id=uuid5(
                    NAMESPACE_URL,
                    f"public-candidate:{selection.candidate_id}:{index}:{observed_at.isoformat()}",
                ),
                provenance=ObservationProvenance(
                    source_type=ObservationSourceType.RECORDED_REPLAY,
                    source_id="licensed-public-trace",
                    recording_id=selection.candidate_id,
                    provider="public-research-source",
                    license_id="manifest-bound",
                ),
                icao_hex=selection.aircraft_identifier,
                observed_at=observed_at,
                received_at=observed_at,
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                altitude_ft=item.get("altitude_ft"),
                ground_speed_knots=item.get("ground_speed_knots"),
                track_degrees=item.get("track_degrees"),
                vertical_rate_fpm=item.get("vertical_rate_fpm"),
                raw_message_id=str(item.get("source_message_id", index)),
            )
        except (KeyError, TypeError, ValueError):
            continue
        usable += 1
        _, events = engine.ingest(observation)
        if abs((observed_at - selection.candidate_time).total_seconds()) <= 60:
            relevant.extend(
                event for event in events if event.evidence.kind in RELEVANT_KINDS
            )
    if usable < 12:
        outcome = PublicOutcome.INSUFFICIENT_DATA
        reason = "Fewer than twelve usable normalized observations remained after validation."
    elif relevant:
        outcome = PublicOutcome.DETECTED
        reason = "The frozen policy opened relevant kinematic integrity evidence near the indexed point."
    else:
        outcome = PublicOutcome.MISSED
        reason = "The trace was sufficient, but the frozen policy opened no relevant evidence near the indexed point."
    return {
        "schema_version": "1.0",
        "candidate_id": selection.candidate_id,
        "outcome": outcome.value,
        "description": "Public research GPS-anomaly candidate correlated with contemporaneous NOTAM data",
        "candidate_time": selection.candidate_time.isoformat().replace("+00:00", "Z"),
        "usable_observations": usable,
        "relevant_evidence": [event.public_dict() for event in relevant],
        "reason": reason,
        "policy_version": policy.policy_version,
        "policy_sha256": hashlib.sha256(Path(policy_path).read_bytes()).hexdigest(),
        "claim_boundary": "This is not evidence of confirmed spoofing or malicious activity.",
    }
