"""Validate sanitized pilot evidence and build an honest aggregate report."""

from __future__ import annotations

import json
import statistics
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


PRIVACY_BOUNDARY = (
    "Aggregate operational evidence only; no aircraft identifiers, receiver label, "
    "coordinates, callsigns, or wall-clock timestamps."
)
COUNTER_FIELDS = (
    "uptime_seconds",
    "source_connected_seconds",
    "parsed_messages_total",
    "parse_failures_total",
    "observations_evaluated_total",
    "dropped_messages_total",
    "reconnects_total",
    "stored_event_count",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


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


class EventType(str, Enum):
    EVIDENCE_OPENED = "evidence_opened"
    EVIDENCE_UPDATED = "evidence_updated"
    EVIDENCE_CLOSED = "evidence_closed"


class ParseFailure(str, Enum):
    ENCODING = "encoding"
    TOO_LONG = "too_long"
    TOO_FEW_FIELDS = "too_few_fields"
    UNSUPPORTED_TYPE = "unsupported_type"
    INVALID_AIRCRAFT_ID = "invalid_aircraft_id"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_VALUE = "invalid_value"


class ReadinessStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"


class KeepInstalled(str, Enum):
    YES = "YES"
    NO = "NO"
    UNSURE = "UNSURE"


class UsefulOutcome(str, Enum):
    OPERATIONAL_FINDING = "OPERATIONAL_FINDING"
    USABILITY_CHANGE = "USABILITY_CHANGE"
    NONE = "NONE"


class OutcomeCode(str, Enum):
    INSTALLABILITY = "INSTALLABILITY"
    RELIABILITY = "RELIABILITY"
    COMPREHENSION = "COMPREHENSION"
    OPERATIONAL_FINDING = "OPERATIONAL_FINDING"
    NO_OBSERVED_VALUE = "NO_OBSERVED_VALUE"
    PRIVACY_CONCERN = "PRIVACY_CONCERN"
    FEATURE_REQUEST = "FEATURE_REQUEST"


class PilotSummary(StrictModel):
    """Exact allow-list for the sidecar's shareable summary schema."""

    schema_version: Literal["1.0"]
    pilot_session_id: str = Field(pattern=r"^[A-Za-z0-9_-]{8,64}$")
    uptime_seconds: int = Field(ge=0)
    source_connected_seconds: int = Field(ge=0)
    source_connected_ratio: float = Field(ge=0, le=1)
    connection: Literal["CONNECTED", "DEGRADED", "DISCONNECTED"]
    policy_version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")
    parsed_messages_total: int = Field(ge=0)
    parse_failures_total: int = Field(ge=0)
    parse_failures_by_reason: dict[ParseFailure, int]
    observations_evaluated_total: int = Field(ge=0)
    dropped_messages_total: int = Field(ge=0)
    reconnects_total: int = Field(ge=0)
    queue_depth: int = Field(ge=0)
    process_memory_mb: float = Field(ge=0, le=4096)
    current_track_state_counts: dict[TrackState, int]
    current_active_evidence_counts: dict[EvidenceKind, int]
    stored_event_count: int = Field(ge=0)
    stored_event_type_counts: dict[EventType, int]
    stored_evidence_kind_counts: dict[EvidenceKind, int]
    privacy_boundary: str

    @field_validator("privacy_boundary")
    @classmethod
    def require_privacy_boundary(cls, value: str) -> str:
        if value != PRIVACY_BOUNDARY:
            raise ValueError("pilot summary privacy boundary is missing or changed")
        return value

    @model_validator(mode="after")
    def validate_aggregate_contract(self) -> "PilotSummary":
        count_maps = (
            self.parse_failures_by_reason,
            self.current_track_state_counts,
            self.current_active_evidence_counts,
            self.stored_event_type_counts,
            self.stored_evidence_kind_counts,
        )
        if any(value < 0 for counts in count_maps for value in counts.values()):
            raise ValueError("aggregate counters cannot be negative")
        if set(self.current_track_state_counts) != set(TrackState):
            raise ValueError("current track state counts must include every state")
        if self.source_connected_seconds > self.uptime_seconds:
            raise ValueError("connected time cannot exceed process uptime")
        if self.observations_evaluated_total > self.parsed_messages_total:
            raise ValueError("evaluated observations cannot exceed parsed messages")
        if sum(self.parse_failures_by_reason.values()) != self.parse_failures_total:
            raise ValueError("parse failure total does not match its reason counts")
        if sum(self.stored_event_type_counts.values()) != self.stored_event_count:
            raise ValueError("stored event total does not match its type counts")
        return self


class DailySnapshot(StrictModel):
    day_index: int = Field(ge=1, le=31)
    summary: PilotSummary


class ParticipantEvidence(StrictModel):
    """Enumeration-only participant evidence; intentionally contains no free text."""

    schema_version: Literal["1.0"] = "1.0"
    participant_id: str = Field(pattern=r"^pilot-[0-9]{2,3}$")
    consent_confirmed: Literal[True]
    privacy_review_confirmed: Literal[True]
    withdrawn: bool
    installation_attempted: bool
    unaided_installation: bool
    installation_minutes_rounded: int | None = Field(default=None, ge=0, le=240)
    readiness_status: ReadinessStatus
    daily_snapshots: tuple[DailySnapshot, ...] = Field(max_length=31)
    state_meanings_explained_correctly: bool
    drops_investigated: bool
    useful_outcome: UsefulOutcome
    keep_installed: KeepInstalled
    outcome_codes: tuple[OutcomeCode, ...] = Field(max_length=7)

    @model_validator(mode="after")
    def validate_participant_evidence(self) -> "ParticipantEvidence":
        if self.installation_attempted != (self.installation_minutes_rounded is not None):
            raise ValueError(
                "installation minutes are required exactly when installation was attempted"
            )
        if not self.installation_attempted and self.unaided_installation:
            raise ValueError("an unattempted installation cannot be unaided")
        if len(set(self.outcome_codes)) != len(self.outcome_codes):
            raise ValueError("outcome codes must be unique")
        days = [item.day_index for item in self.daily_snapshots]
        if days != list(range(1, len(days) + 1)):
            raise ValueError("daily snapshots must use consecutive day indexes starting at 1")
        if not self.withdrawn and not self.daily_snapshots:
            raise ValueError("active participants require at least one daily snapshot")
        self._validate_sessions()
        return self

    def _validate_sessions(self) -> None:
        closed_sessions: set[str] = set()
        previous: PilotSummary | None = None
        for item in self.daily_snapshots:
            current = item.summary
            if previous is not None and current.pilot_session_id != previous.pilot_session_id:
                closed_sessions.add(previous.pilot_session_id)
            if current.pilot_session_id in closed_sessions:
                raise ValueError("a process session cannot reappear after a restart")
            if previous is not None and current.pilot_session_id == previous.pilot_session_id:
                for field in COUNTER_FIELDS:
                    if getattr(current, field) < getattr(previous, field):
                        raise ValueError(f"{field} decreased within one process session")
            previous = current
        policies = {item.summary.policy_version for item in self.daily_snapshots}
        if len(policies) > 1:
            raise ValueError("a participant cannot change policy during the field run")

    @property
    def completed_seven_days(self) -> bool:
        return not self.withdrawn and len(self.daily_snapshots) >= 7


def load_participant_evidence(path: Path) -> ParticipantEvidence:
    text = path.read_text(encoding="utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("participant evidence must be a JSON object")
    return ParticipantEvidence.model_validate_json(text)


def build_pilot_report(
    participants: Sequence[ParticipantEvidence],
) -> dict[str, Any]:
    if not participants:
        raise ValueError("at least one participant evidence bundle is required")
    participant_ids = [item.participant_id for item in participants]
    if len(set(participant_ids)) != len(participant_ids):
        raise ValueError("participant IDs must be unique")

    attempted = [item for item in participants if item.installation_attempted]
    unaided_minutes = [
        item.installation_minutes_rounded
        for item in attempted
        if item.unaided_installation and item.installation_minutes_rounded is not None
    ]
    completed = [item for item in participants if item.completed_seven_days]
    median_minutes = (
        round(float(statistics.median(unaided_minutes)), 1) if unaided_minutes else None
    )
    completed_policies = {
        snapshot.summary.policy_version
        for item in completed
        for snapshot in item.daily_snapshots
    }
    checks = {
        "at_least_three_installation_attempts": len(attempted) >= 3,
        "at_least_two_seven_day_completions": len(completed) >= 2,
        "median_unaided_installation_at_most_15_minutes": (
            median_minutes is not None and median_minutes <= 15
        ),
        "completed_participants_understand_state_meanings": (
            bool(completed)
            and all(item.state_meanings_explained_correctly for item in completed)
        ),
        "completed_participants_passed_readiness": (
            bool(completed)
            and all(item.readiness_status is ReadinessStatus.READY for item in completed)
        ),
        "reported_drops_investigated": (
            bool(completed)
            and all(
                not _has_drops(item) or item.drops_investigated for item in completed
            )
        ),
        "at_least_one_useful_outcome": any(
            not item.withdrawn and item.useful_outcome is not UsefulOutcome.NONE
            for item in participants
        ),
        "single_frozen_policy_for_completed_runs": (
            bool(completed_policies) and len(completed_policies) == 1
        ),
        "all_shared_bundles_privacy_reviewed": all(
            item.privacy_review_confirmed for item in participants
        ),
    }
    success = all(checks.values())
    totals = _aggregate_counters(participants)
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "PILOT_SUCCESS" if success else "PILOT_INCOMPLETE",
        "claim_scope": (
            "independent_deployability_reliability_comprehension_and_operational_usefulness"
            if success
            else "pilot_criteria_not_met"
        ),
        "claim": (
            "Independent ADS-B feeder operators installed and evaluated the local "
            "integrity sidecar; the pilot measured deployability, reliability, "
            "comprehension, and operational usefulness."
            if success
            else "The available evidence does not yet satisfy the independent pilot criteria."
        ),
        "participants": {
            "bundles": len(participants),
            "installation_attempts": len(attempted),
            "seven_day_completions": len(completed),
            "withdrawals": sum(item.withdrawn for item in participants),
            "median_unaided_installation_minutes": median_minutes,
            "runs": [
                {
                    "participant_id": item.participant_id,
                    "days_reported": len(item.daily_snapshots),
                    "completed_seven_days": item.completed_seven_days,
                    "withdrawn": item.withdrawn,
                    "keep_installed": item.keep_installed.value,
                    "useful_outcome": item.useful_outcome.value,
                    "outcome_codes": sorted(code.value for code in item.outcome_codes),
                }
                for item in participants
            ],
        },
        "aggregate_operations": totals,
        "success_criteria": checks,
        "limitations": [
            "The pilot does not establish that the detector catches spoofing.",
            "The pilot does not establish verified aircraft truth or a field false-positive rate.",
            "Daily indexes and interview answers are participant-reported, not independently attested.",
            "Only aggregate allow-listed sidecar summaries were accepted; raw traffic was excluded.",
        ],
    }
    return report


def _has_drops(participant: ParticipantEvidence) -> bool:
    return any(
        item.summary.dropped_messages_total > 0
        for item in participant.daily_snapshots
    )


def _aggregate_counters(
    participants: Sequence[ParticipantEvidence],
) -> dict[str, Any]:
    totals = {field: 0 for field in COUNTER_FIELDS}
    peak_memory_mb = 0.0
    days_with_questionable_tracks = 0
    for participant in participants:
        previous: PilotSummary | None = None
        for item in participant.daily_snapshots:
            current = item.summary
            new_session = (
                previous is None
                or current.pilot_session_id != previous.pilot_session_id
            )
            for field in COUNTER_FIELDS:
                value = int(getattr(current, field))
                prior = 0 if new_session else int(getattr(previous, field))
                totals[field] += value - prior
            peak_memory_mb = max(peak_memory_mb, current.process_memory_mb)
            if current.current_track_state_counts[TrackState.QUESTIONABLE] > 0:
                days_with_questionable_tracks += 1
            previous = current
    uptime = totals["uptime_seconds"]
    connected = totals["source_connected_seconds"]
    return {
        **totals,
        "source_connected_ratio": round(connected / uptime, 6) if uptime else 0.0,
        "peak_process_memory_mb": round(peak_memory_mb, 3),
        "daily_snapshots_with_questionable_tracks": days_with_questionable_tracks,
    }


def render_pilot_report_markdown(report: dict[str, Any]) -> str:
    criteria = report["success_criteria"]
    participants = report["participants"]
    operations = report["aggregate_operations"]
    lines = [
        "# Independent feeder pilot report",
        "",
        f"Status: **{report['status']}**",
        "",
        str(report["claim"]),
        "",
        "## Participation",
        "",
        f"- Installation attempts: {participants['installation_attempts']}",
        f"- Seven-day completions: {participants['seven_day_completions']}",
        f"- Withdrawals: {participants['withdrawals']}",
        "- Median unaided installation time: "
        f"{participants['median_unaided_installation_minutes']}",
        "",
        "## Success criteria",
        "",
        "| Criterion | Result |",
        "|---|---|",
    ]
    lines.extend(
        f"| {name.replace('_', ' ')} | {'PASS' if passed else 'NOT MET'} |"
        for name, passed in criteria.items()
    )
    lines.extend(
        [
            "",
            "## Aggregate operations",
            "",
            f"- Parsed messages: {operations['parsed_messages_total']}",
            f"- Evaluated observations: {operations['observations_evaluated_total']}",
            f"- Reported drops: {operations['dropped_messages_total']}",
            f"- Reconnects: {operations['reconnects_total']}",
            f"- Aggregate connection ratio: {operations['source_connected_ratio']}",
            f"- Peak process memory (MB): {operations['peak_process_memory_mb']}",
            "",
            "## Limitations",
            "",
        ]
    )
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    return "\n".join(lines) + "\n"
