"""Read-only API for deterministic aircraft-integrity evidence."""

from datetime import datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.kinematics import KinematicEvaluationRecord, WindowKinematicEvaluationRecord


router = APIRouter(prefix="/kinematics", tags=["kinematics"])


class KinematicRuleResponse(BaseModel):
    rule: Literal[
        "IMPLIED_GROUND_SPEED",
        "REPORTED_ACCELERATION",
        "TURN_RATE",
        "DERIVED_VERTICAL_RATE",
        "SPEED_DISAGREEMENT",
    ]
    status: Literal["PASS", "FLAGGED"]
    value: float
    threshold: float
    unit: str
    explanation: str
    observation_ids: list[UUID]


class KinematicEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: UUID
    policy_version: str
    previous_observation_id: UUID
    current_observation_id: UUID
    source_type: str
    source_id: str
    icao_hex: str
    evaluated_at: datetime
    status: Literal["PASS", "FLAGGED", "INSUFFICIENT_DATA"]
    reason: str | None
    delta_seconds: float
    measurements: dict[str, float]
    rule_results: list[KinematicRuleResponse]


class WindowRuleResponse(BaseModel):
    rule: Literal["CUMULATIVE_POSITION_RESIDUAL"]
    status: Literal["PASS", "FLAGGED"]
    value: float
    threshold: float
    unit: str
    explanation: str
    observation_ids: list[UUID]


class WindowEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evaluation_id: UUID
    policy_version: str
    first_observation_id: UUID
    current_observation_id: UUID
    observation_ids: list[UUID]
    source_type: str
    source_id: str
    icao_hex: str
    evaluated_at: datetime
    status: Literal["PASS", "FLAGGED", "INSUFFICIENT_DATA"]
    reason: str | None
    duration_seconds: float
    measurements: dict[str, float]
    rule_results: list[WindowRuleResponse]


@router.get("/evaluations", response_model=list[KinematicEvaluationResponse])
def get_kinematic_evaluations(
    icao_hex: str | None = Query(default=None, pattern=r"^[0-9A-Fa-f]{6}$"),
    source_id: str | None = Query(default=None, min_length=1, max_length=100),
    status: Literal["PASS", "FLAGGED", "INSUFFICIENT_DATA"] | None = None,
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[KinematicEvaluationRecord]:
    """Return versioned evidence, optionally filtered by aircraft and result."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = db.query(KinematicEvaluationRecord).filter(
        KinematicEvaluationRecord.evaluated_at >= cutoff
    )
    if icao_hex:
        query = query.filter(KinematicEvaluationRecord.icao_hex == icao_hex.upper())
    if source_id:
        query = query.filter(KinematicEvaluationRecord.source_id == source_id)
    if status:
        query = query.filter(KinematicEvaluationRecord.status == status)
    return query.order_by(KinematicEvaluationRecord.evaluated_at.desc()).limit(limit).all()


@router.get("/window-evaluations", response_model=list[WindowEvaluationResponse])
def get_window_evaluations(
    icao_hex: str | None = Query(default=None, pattern=r"^[0-9A-Fa-f]{6}$"),
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[WindowKinematicEvaluationRecord]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    query = db.query(WindowKinematicEvaluationRecord).filter(
        WindowKinematicEvaluationRecord.evaluated_at >= cutoff
    )
    if icao_hex:
        query = query.filter(WindowKinematicEvaluationRecord.icao_hex == icao_hex.upper())
    return query.order_by(WindowKinematicEvaluationRecord.evaluated_at.desc()).limit(limit).all()
