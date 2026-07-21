"""Idempotent storage and ingestion integration for kinematic evidence."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models.kinematics import KinematicEvaluationRecord
from .kinematics import KinematicEvaluation


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
