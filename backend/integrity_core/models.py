"""Versioned public value objects for integrity evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TrackState(str, Enum):
    NOMINAL = "NOMINAL"
    QUESTIONABLE = "QUESTIONABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class EvidenceKind(str, Enum):
    PAIR_KINEMATIC = "PAIR_KINEMATIC"
    WINDOW_KINEMATIC = "WINDOW_KINEMATIC"
    TIMING_DUPLICATE = "TIMING_DUPLICATE"
    TIMING_NON_INCREASING = "TIMING_NON_INCREASING"
    TIMING_OUT_OF_ORDER = "TIMING_OUT_OF_ORDER"
    TIMING_EXCESSIVE_LATENCY = "TIMING_EXCESSIVE_LATENCY"
    TIMING_GAP = "TIMING_GAP"


class EvidenceSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class EventType(str, Enum):
    EVIDENCE_OPENED = "evidence_opened"
    EVIDENCE_UPDATED = "evidence_updated"
    EVIDENCE_CLOSED = "evidence_closed"


def utc_text(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class IntegrityEvidence:
    evidence_id: str
    kind: EvidenceKind
    severity: EvidenceSeverity
    first_observed_at: datetime
    last_observed_at: datetime
    expires_at: datetime
    summary: str
    measured: dict[str, float] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)

    def public_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "kind": self.kind.value,
            "severity": self.severity.value,
            "first_observed_at": utc_text(self.first_observed_at),
            "last_observed_at": utc_text(self.last_observed_at),
            "summary": self.summary,
            "measured": self.measured,
            "thresholds": self.thresholds,
        }


@dataclass(frozen=True)
class IntegritySnapshotV1:
    track_id: str
    observed_at: datetime
    state: TrackState
    observation_count: int
    window_seconds: float
    policy_version: str
    active_evidence: tuple[IntegrityEvidence, ...]
    limitations: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "track_id": self.track_id,
            "observed_at": utc_text(self.observed_at),
            "state": self.state.value,
            "observation_count": self.observation_count,
            "window_seconds": self.window_seconds,
            "policy_version": self.policy_version,
            "active_evidence": [item.public_dict() for item in self.active_evidence],
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True)
class IntegrityEvent:
    event_id: str
    event_type: EventType
    observed_at: datetime
    track_id: str
    state: TrackState
    evidence: IntegrityEvidence

    def public_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "observed_at": utc_text(self.observed_at),
            "track_id": self.track_id,
            "state": self.state.value,
            "evidence": self.evidence.public_dict(),
        }
