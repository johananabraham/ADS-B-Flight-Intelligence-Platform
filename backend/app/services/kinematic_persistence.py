"""Idempotent storage and ingestion integration for kinematic evidence."""

from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models.aircraft import (
    Anomaly,
    AnomalyCategory,
    AnomalySeverity,
    AnomalyType,
)
from ..models.kinematics import (
    KinematicEvaluationRecord,
    WindowKinematicEvaluationRecord,
)
from ..models.observation import TrackObservationRecord
from ..schemas.observation import (
    ObservationProvenance,
    ObservationQualityFlag,
    ObservationSourceType,
    TrackObservation,
)
from integrity_core.evaluators import (
    EvaluationStatus,
    KinematicEvaluation,
    WindowEvaluation,
    WindowPolicy,
    evaluate_pair,
    evaluate_window,
)


def evaluation_values(evaluation: KinematicEvaluation) -> dict[str, object]:
    return {
        "evaluation_id": evaluation.evaluation_id,
        "policy_version": evaluation.policy_version,
        "previous_observation_id": evaluation.previous_observation_id,
        "current_observation_id": evaluation.current_observation_id,
        "source_type": evaluation.source_type,
        "source_id": evaluation.source_id,
        "icao_hex": evaluation.icao_hex,
        "evaluated_at": evaluation.evaluated_at,
        "status": evaluation.status.value,
        "reason": evaluation.reason,
        "delta_seconds": evaluation.delta_seconds,
        "measurements": evaluation.measurements,
        "rule_results": [result.to_dict() for result in evaluation.rule_results],
    }


def build_evaluation_insert_statement(evaluation: KinematicEvaluation):
    return (
        insert(KinematicEvaluationRecord)
        .values(**evaluation_values(evaluation))
        .on_conflict_do_nothing(index_elements=["evaluation_id"])
    )


def insert_evaluation(db: Session, evaluation: KinematicEvaluation) -> bool:
    result = db.execute(build_evaluation_insert_statement(evaluation))
    return result.rowcount == 1


def window_evaluation_values(evaluation: WindowEvaluation) -> dict[str, object]:
    return {
        "evaluation_id": evaluation.evaluation_id,
        "policy_version": evaluation.policy_version,
        "first_observation_id": evaluation.observation_ids[0],
        "current_observation_id": evaluation.observation_ids[-1],
        "observation_ids": [str(value) for value in evaluation.observation_ids],
        "source_type": evaluation.source_type,
        "source_id": evaluation.source_id,
        "icao_hex": evaluation.icao_hex,
        "evaluated_at": evaluation.evaluated_at,
        "status": evaluation.status.value,
        "reason": evaluation.reason,
        "duration_seconds": evaluation.duration_seconds,
        "measurements": evaluation.measurements,
        "rule_results": [result.to_dict() for result in evaluation.rule_results],
    }


def build_window_evaluation_insert_statement(evaluation: WindowEvaluation):
    return (
        insert(WindowKinematicEvaluationRecord)
        .values(**window_evaluation_values(evaluation))
        .on_conflict_do_nothing(index_elements=["evaluation_id"])
    )


def insert_window_evaluation(db: Session, evaluation: WindowEvaluation) -> bool:
    result = db.execute(build_window_evaluation_insert_statement(evaluation))
    return result.rowcount == 1


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def record_to_observation(record: TrackObservationRecord) -> TrackObservation:
    """Restore the shared contract from one immutable database record."""
    return TrackObservation(
        schema_version=record.schema_version,
        observation_id=record.observation_id,
        provenance=ObservationProvenance(
            source_type=ObservationSourceType(record.source_type),
            source_id=record.source_id,
            receiver_id=record.receiver_id,
            recording_id=record.recording_id,
            provider=record.provider,
            license_id=record.license_id,
        ),
        icao_hex=record.icao_hex,
        observed_at=_as_utc(record.observed_at),
        received_at=_as_utc(record.received_at),
        callsign=record.callsign,
        latitude=record.latitude,
        longitude=record.longitude,
        altitude_ft=record.altitude_ft,
        ground_speed_knots=record.ground_speed_knots,
        track_degrees=record.track_degrees,
        vertical_rate_fpm=record.vertical_rate_fpm,
        squawk=record.squawk,
        quality_flags=frozenset(ObservationQualityFlag(value) for value in record.quality_flags),
        raw_message_id=record.raw_message_id,
    )


def find_previous_position_observation(
    db: Session, current: TrackObservation
) -> TrackObservation | None:
    """Find the prior complete position from the same aircraft and source."""
    record = (
        db.query(TrackObservationRecord)
        .filter(
            TrackObservationRecord.icao_hex == current.icao_hex,
            TrackObservationRecord.source_type == current.provenance.source_type.value,
            TrackObservationRecord.source_id == current.provenance.source_id,
            TrackObservationRecord.receiver_id == current.provenance.receiver_id,
            TrackObservationRecord.recording_id == current.provenance.recording_id,
            TrackObservationRecord.provider == current.provenance.provider,
            TrackObservationRecord.license_id == current.provenance.license_id,
            TrackObservationRecord.observation_id != current.observation_id,
            TrackObservationRecord.observed_at < current.observed_at,
            TrackObservationRecord.latitude.is_not(None),
            TrackObservationRecord.longitude.is_not(None),
        )
        .order_by(TrackObservationRecord.observed_at.desc())
        .first()
    )
    return record_to_observation(record) if record else None


def find_window_observations(
    db: Session,
    current: TrackObservation,
    *,
    policy: WindowPolicy | None = None,
) -> tuple[TrackObservation, ...]:
    selected_policy = policy or WindowPolicy()
    cutoff = current.observed_at.timestamp() - selected_policy.maximum_duration_seconds
    records = (
        db.query(TrackObservationRecord)
        .filter(
            TrackObservationRecord.icao_hex == current.icao_hex,
            TrackObservationRecord.source_type == current.provenance.source_type.value,
            TrackObservationRecord.source_id == current.provenance.source_id,
            TrackObservationRecord.receiver_id == current.provenance.receiver_id,
            TrackObservationRecord.recording_id == current.provenance.recording_id,
            TrackObservationRecord.provider == current.provenance.provider,
            TrackObservationRecord.license_id == current.provenance.license_id,
            TrackObservationRecord.observed_at <= current.observed_at,
            TrackObservationRecord.observed_at
            >= datetime.fromtimestamp(cutoff, tz=timezone.utc),
        )
        .order_by(TrackObservationRecord.observed_at.desc())
        .limit(selected_policy.maximum_observations)
        .all()
    )
    return tuple(record_to_observation(record) for record in reversed(records))


def evaluation_to_anomaly(
    evaluation: KinematicEvaluation, current: TrackObservation
) -> Anomaly:
    """Create an operator alert that preserves the underlying rule evidence."""
    failed_rules = [result.to_dict() for result in evaluation.failed_rules]
    severity = (
        AnomalySeverity.HIGH if len(failed_rules) >= 2 else AnomalySeverity.MEDIUM
    )
    return Anomaly(
        icao_hex=current.icao_hex,
        callsign=current.callsign,
        anomaly_type=AnomalyType.KINEMATIC_PLAUSIBILITY,
        severity=severity,
        category=AnomalyCategory.INTEGRITY_EVIDENCE,
        latitude=current.latitude,
        longitude=current.longitude,
        altitude=current.altitude_ft,
        detected_at=current.received_at,
        description=(
            f"{len(failed_rules)} kinematic rule(s) exceeded policy limits; "
            "this indicates inconsistent data, not proof of spoofing."
        ),
        details={
            "evaluation_id": str(evaluation.evaluation_id),
            "policy_version": evaluation.policy_version,
            "previous_observation_id": str(evaluation.previous_observation_id),
            "current_observation_id": str(evaluation.current_observation_id),
            "source_type": evaluation.source_type,
            "source_id": evaluation.source_id,
            "measurements": evaluation.measurements,
            "failed_rules": failed_rules,
            "interpretation": "Kinematic inconsistency; intent is not established.",
        },
    )


def evaluate_new_observation(
    db: Session, current: TrackObservation
) -> KinematicEvaluation | None:
    """Evaluate and persist a newly inserted position observation exactly once."""
    if current.latitude is None:
        return None
    previous = find_previous_position_observation(db, current)
    if previous is None:
        return None

    evaluation = evaluate_pair(previous, current)
    if insert_evaluation(db, evaluation) and evaluation.status is EvaluationStatus.FLAGGED:
        db.add(evaluation_to_anomaly(evaluation, current))
    window_observations = find_window_observations(db, current)
    if len(window_observations) >= WindowPolicy().minimum_observations:
        insert_window_evaluation(db, evaluate_window(window_observations))
    return evaluation
