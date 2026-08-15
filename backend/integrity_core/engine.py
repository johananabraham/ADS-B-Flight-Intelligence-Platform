"""Deterministic, bounded integrity evidence aggregation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import UUID, uuid5

from app.schemas.observation import ObservationSourceType, TrackObservation
from .evaluators import EvaluationStatus, evaluate_pair, evaluate_window
from .models import (
    EventType,
    EvidenceKind,
    EvidenceSeverity,
    IntegrityEvent,
    IntegrityEvidence,
    IntegritySnapshotV1,
    TrackState,
)
from .policy import IntegrityPolicy


TRACK_NAMESPACE = UUID("cd8b2f27-f6aa-4c0f-9a86-ad751f134def")
EVIDENCE_NAMESPACE = UUID("b046df2b-77bc-49f8-93ae-7d49cfafec37")
EVENT_NAMESPACE = UUID("4309d0fb-d55e-4199-9219-7e7932285348")


@dataclass
class _Track:
    observations: deque[TrackObservation]
    active: dict[str, IntegrityEvidence]
    seen_message_ids: set[str]
    seen_message_order: deque[str]


class IntegrityEngine:
    """Evaluate observations without persistence or transport dependencies."""

    def __init__(self, policy: IntegrityPolicy) -> None:
        self.policy = policy
        self._tracks: dict[str, _Track] = {}
        self._snapshots: dict[str, IntegritySnapshotV1] = {}

    @staticmethod
    def track_id(observation: TrackObservation) -> str:
        identity = (
            f"{observation.provenance.source_type.value}:"
            f"{observation.provenance.source_id}:{observation.icao_hex}"
        )
        return str(uuid5(TRACK_NAMESPACE, identity))

    def snapshots(self) -> tuple[IntegritySnapshotV1, ...]:
        return tuple(
            sorted(
                self._snapshots.values(),
                key=lambda item: (item.observed_at, item.track_id),
                reverse=True,
            )
        )

    def snapshot(self, track_id: str) -> IntegritySnapshotV1 | None:
        return self._snapshots.get(track_id)

    def ingest(
        self, observation: TrackObservation
    ) -> tuple[IntegritySnapshotV1, tuple[IntegrityEvent, ...]]:
        track_id = self.track_id(observation)
        self._purge_inactive(observation.observed_at)
        self._evict_if_needed(track_id)
        track = self._tracks.setdefault(
            track_id,
            _Track(
                observations=deque(
                    maxlen=self.policy.runtime.maximum_observations_per_track
                ),
                active={},
                seen_message_ids=set(),
                seen_message_order=deque(
                    maxlen=self.policy.runtime.maximum_observations_per_track
                ),
            ),
        )
        events = self._expire(track_id, track, observation.observed_at)
        previous = track.observations[-1] if track.observations else None

        candidates: list[tuple[EvidenceKind, str, str, dict[str, float], dict[str, float], EvidenceSeverity]] = []
        raw_id = observation.raw_message_id
        is_duplicate = bool(raw_id and raw_id in track.seen_message_ids)
        if is_duplicate:
            candidates.append(
                (
                    EvidenceKind.TIMING_DUPLICATE,
                    "message",
                    "A duplicate normalized source message was observed.",
                    {"duplicate_count": 1.0},
                    {"duplicate_count": 0.0},
                    EvidenceSeverity.WARNING,
                )
            )
        if raw_id and not is_duplicate:
            if (
                track.seen_message_order.maxlen
                and len(track.seen_message_order) == track.seen_message_order.maxlen
            ):
                track.seen_message_ids.discard(track.seen_message_order[0])
            track.seen_message_order.append(raw_id)
            track.seen_message_ids.add(raw_id)

        if previous is not None:
            delta = (observation.observed_at - previous.observed_at).total_seconds()
            if delta <= 0:
                candidates.append(
                    (
                        EvidenceKind.TIMING_NON_INCREASING,
                        "source_time",
                        "Source event time did not advance between observations.",
                        {"delta_seconds": round(delta, 3)},
                        {"minimum_delta_seconds": 0.0},
                        EvidenceSeverity.WARNING,
                    )
                )
            if delta < -self.policy.timing.maximum_reordering_seconds:
                candidates.append(
                    (
                        EvidenceKind.TIMING_OUT_OF_ORDER,
                        "source_time",
                        "An observation arrived outside the permitted reordering window.",
                        {"reordering_seconds": round(abs(delta), 3)},
                        {
                            "maximum_reordering_seconds": self.policy.timing.maximum_reordering_seconds
                        },
                        EvidenceSeverity.WARNING,
                    )
                )
            if delta > self.policy.timing.gap_seconds:
                candidates.append(
                    (
                        EvidenceKind.TIMING_GAP,
                        "continuity",
                        "The track observation gap exceeded the continuity policy.",
                        {"gap_seconds": round(delta, 3)},
                        {"maximum_gap_seconds": self.policy.timing.gap_seconds},
                        EvidenceSeverity.INFO,
                    )
                )

            pair = evaluate_pair(previous, observation, policy=self.policy.pair)
            for result in pair.failed_rules:
                severity = self._severity(result.value, result.threshold)
                candidates.append(
                    (
                        EvidenceKind.PAIR_KINEMATIC,
                        result.rule.value,
                        result.explanation,
                        {result.rule.value.lower(): result.value},
                        {result.rule.value.lower(): result.threshold},
                        severity,
                    )
                )

        if observation.provenance.source_type is not ObservationSourceType.RECORDED_REPLAY:
            latency = (observation.received_at - observation.observed_at).total_seconds()
            if latency > self.policy.timing.maximum_latency_seconds:
                candidates.append(
                    (
                        EvidenceKind.TIMING_EXCESSIVE_LATENCY,
                        "source_latency",
                        "Source-to-receiver latency exceeded the policy threshold.",
                        {"latency_seconds": round(latency, 3)},
                        {"maximum_latency_seconds": self.policy.timing.maximum_latency_seconds},
                        EvidenceSeverity.WARNING,
                    )
                )

        track.observations.append(observation)
        earliest_window_time = observation.observed_at - timedelta(
            seconds=self.policy.window.maximum_duration_seconds
        )
        window_items = tuple(
            item
            for item in track.observations
            if earliest_window_time <= item.observed_at <= observation.observed_at
        )[-self.policy.window.maximum_observations :]
        if len(window_items) >= self.policy.window.minimum_observations:
            window_evaluation = evaluate_window(window_items, policy=self.policy.window)
            if window_evaluation.status is EvaluationStatus.FLAGGED:
                for window_rule in window_evaluation.failed_rules:
                    candidates.append(
                        (
                            EvidenceKind.WINDOW_KINEMATIC,
                            window_rule.rule.value,
                            window_rule.explanation,
                            {window_rule.rule.value.lower(): window_rule.value},
                            {window_rule.rule.value.lower(): window_rule.threshold},
                            self._severity(window_rule.value, window_rule.threshold),
                        )
                    )

        for candidate in candidates:
            events.append(self._open_or_update(track_id, track, observation, *candidate))
        snapshot = self._build_snapshot(track_id, track)
        self._snapshots[track_id] = snapshot
        return snapshot, tuple(events)

    @staticmethod
    def _severity(value: float, threshold: float) -> EvidenceSeverity:
        if threshold > 0 and value >= threshold * 2:
            return EvidenceSeverity.CRITICAL
        return EvidenceSeverity.WARNING

    def _open_or_update(
        self,
        track_id: str,
        track: _Track,
        observation: TrackObservation,
        kind: EvidenceKind,
        discriminator: str,
        summary: str,
        measured: dict[str, float],
        thresholds: dict[str, float],
        severity: EvidenceSeverity,
    ) -> IntegrityEvent:
        key = f"{kind.value}:{discriminator}"
        existing = track.active.get(key)
        if existing is None:
            evidence_id = str(
                uuid5(
                    EVIDENCE_NAMESPACE,
                    f"{self.policy.policy_version}:{track_id}:{key}:{observation.observation_id}",
                )
            )
            evidence = IntegrityEvidence(
                evidence_id=evidence_id,
                kind=kind,
                severity=severity,
                first_observed_at=observation.observed_at,
                last_observed_at=observation.observed_at,
                expires_at=observation.observed_at
                + timedelta(seconds=self.policy.timing.evidence_ttl_seconds),
                summary=summary,
                measured=measured,
                thresholds=thresholds,
            )
            event_type = EventType.EVIDENCE_OPENED
        else:
            evidence = replace(
                existing,
                severity=max(existing.severity, severity, key=lambda item: list(EvidenceSeverity).index(item)),
                last_observed_at=observation.observed_at,
                expires_at=observation.observed_at
                + timedelta(seconds=self.policy.timing.evidence_ttl_seconds),
                summary=summary,
                measured=measured,
                thresholds=thresholds,
            )
            event_type = EventType.EVIDENCE_UPDATED
        track.active[key] = evidence
        return self._event(event_type, track_id, observation.observed_at, evidence)

    def _expire(self, track_id: str, track: _Track, now: datetime) -> list[IntegrityEvent]:
        events: list[IntegrityEvent] = []
        for key, evidence in sorted(tuple(track.active.items())):
            if evidence.expires_at <= now:
                del track.active[key]
                events.append(self._event(EventType.EVIDENCE_CLOSED, track_id, now, evidence))
        return events

    def _event(
        self,
        event_type: EventType,
        track_id: str,
        observed_at: datetime,
        evidence: IntegrityEvidence,
    ) -> IntegrityEvent:
        identity = f"{event_type.value}:{evidence.evidence_id}:{observed_at.isoformat()}"
        state = TrackState.QUESTIONABLE if event_type is not EventType.EVIDENCE_CLOSED else TrackState.NOMINAL
        return IntegrityEvent(
            event_id=str(uuid5(EVENT_NAMESPACE, identity)),
            event_type=event_type,
            observed_at=observed_at,
            track_id=track_id,
            state=state,
            evidence=evidence,
        )

    def _build_snapshot(self, track_id: str, track: _Track) -> IntegritySnapshotV1:
        observations = tuple(track.observations)
        current = observations[-1]
        limitations: list[str] = []
        if len(observations) < self.policy.runtime.minimum_observations:
            limitations.append(
                f"At least {self.policy.runtime.minimum_observations} observations are required."
            )
        if current.latitude is None:
            limitations.append("The latest observation has no complete position.")
        if len(observations) < self.policy.window.minimum_observations:
            limitations.append("The trajectory window is not yet long enough for gradual-drift evaluation.")
        if len(observations) < self.policy.runtime.minimum_observations:
            state = TrackState.INSUFFICIENT_DATA
        elif track.active:
            state = TrackState.QUESTIONABLE
        else:
            state = TrackState.NOMINAL
        duration = (
            current.observed_at - observations[0].observed_at
        ).total_seconds()
        return IntegritySnapshotV1(
            track_id=track_id,
            observed_at=current.observed_at,
            state=state,
            observation_count=len(observations),
            window_seconds=round(max(duration, 0.0), 3),
            policy_version=self.policy.policy_version,
            active_evidence=tuple(
                sorted(track.active.values(), key=lambda item: (item.kind.value, item.evidence_id))
            ),
            limitations=tuple(limitations),
        )

    def _evict_if_needed(self, incoming_track_id: str) -> None:
        if incoming_track_id in self._tracks:
            return
        while len(self._tracks) >= self.policy.runtime.maximum_tracks:
            oldest_id = min(
                self._tracks,
                key=lambda item: (
                    self._tracks[item].observations[-1].observed_at,
                    item,
                ),
            )
            del self._tracks[oldest_id]
            self._snapshots.pop(oldest_id, None)

    def _purge_inactive(self, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.policy.runtime.inactive_track_seconds)
        stale = sorted(
            track_id
            for track_id, track in self._tracks.items()
            if track.observations[-1].observed_at < cutoff
        )
        for track_id in stale:
            del self._tracks[track_id]
            self._snapshots.pop(track_id, None)
