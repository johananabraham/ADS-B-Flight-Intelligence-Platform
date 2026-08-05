"""Explainable aircraft trust assessment over independently stored evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.database import get_db
from ..models.edge import SensorNodeRecord
from ..models.kinematics import KinematicEvaluationRecord, WindowKinematicEvaluationRecord
from ..models.observation import TrackObservationRecord
from ..services.corroboration import CorroborationResult, compare_observations
from ..services.corroboration_service import CorroborationService
from ..services.kinematic_persistence import record_to_observation
from ..services.kinematics import EvaluationStatus
from ..services.station_health import StationHealthResult
from ..services.station_records import evaluate_station_record
from ..services.trust_assessment import (
    TrustAssessmentInputs,
    TrustAssessmentResult,
    assess_trust,
)
from ..services.trust_persistence import create_snapshot, insert_snapshot
from .corroboration import get_corroboration_service


router = APIRouter(prefix="/trust", tags=["trust"])


class TrustComponentResponse(BaseModel):
    component: Literal["PAIR_KINEMATICS", "WINDOW_KINEMATICS", "CORROBORATION", "STATION", "ML"]
    state: str
    policy_version: str | None
    evaluated_at: datetime | None
    age_seconds: float | None
    evidence_ids: tuple[str, ...]
    reasons: tuple[str, ...]


class TrustAssessmentResponse(BaseModel):
    state: Literal["TRUSTED", "QUESTIONABLE", "LOW_CONFIDENCE", "INSUFFICIENT_DATA"]
    policy_version: str
    icao_hex: str
    evaluated_at: datetime
    reasons: tuple[str, ...]
    components: tuple[TrustComponentResponse, ...]
    numeric_score: None = None


class PersistedTrustAssessmentResponse(BaseModel):
    assessment_id: UUID
    inserted: bool
    assessment: TrustAssessmentResponse


@router.get("/{icao_hex}", response_model=TrustAssessmentResponse)
async def get_trust_assessment(
    icao_hex: str,
    db: Session = Depends(get_db),
    corroboration_service: CorroborationService = Depends(get_corroboration_service),
) -> TrustAssessmentResponse:
    response, _assessment = await _evaluate_trust(
        icao_hex, db, corroboration_service
    )
    return response


@router.post(
    "/{icao_hex}/assessments", response_model=PersistedTrustAssessmentResponse
)
async def create_trust_assessment(
    icao_hex: str,
    db: Session = Depends(get_db),
    corroboration_service: CorroborationService = Depends(get_corroboration_service),
) -> PersistedTrustAssessmentResponse:
    response, assessment = await _evaluate_trust(
        icao_hex, db, corroboration_service
    )
    snapshot = create_snapshot(
        assessment,
        tuple(component.model_dump(mode="json") for component in response.components),
    )
    inserted = insert_snapshot(db, snapshot)
    db.commit()
    return PersistedTrustAssessmentResponse(
        assessment_id=snapshot.assessment_id,
        inserted=inserted,
        assessment=response,
    )


async def _evaluate_trust(
    icao_hex: str,
    db: Session,
    corroboration_service: CorroborationService,
) -> tuple[TrustAssessmentResponse, TrustAssessmentResult]:
    normalized = _normalize_icao(icao_hex)
    now = datetime.now(timezone.utc)
    pair = _latest_pair(db, normalized)
    window = _latest_window(db, normalized)
    local = _latest_local_observation(db, normalized)
    corroboration = await _corroborate(local, now, corroboration_service)
    source_id = pair.source_id if pair else window.source_id if window else None
    station_record = _station_record(db, source_id)
    station = (
        evaluate_station_record(station_record, evaluated_at=now)
        if station_record
        else None
    )

    inputs = TrustAssessmentInputs(
        icao_hex=normalized,
        evaluated_at=now,
        pair_status=EvaluationStatus(pair.status) if pair else None,
        window_status=EvaluationStatus(window.status) if window else None,
        corroboration_state=corroboration.state if corroboration else None,
        station_state=station.state if station else None,
        pair_evaluation_id=str(pair.evaluation_id) if pair else None,
        window_evaluation_id=str(window.evaluation_id) if window else None,
        local_observation_id=corroboration.local_observation_id if corroboration else None,
        external_observation_id=(
            corroboration.external_observation_id if corroboration else None
        ),
        station_node_id=station.node_id if station else None,
    )
    assessment = assess_trust(inputs)
    response = TrustAssessmentResponse(
        state=assessment.state.value,
        policy_version=assessment.policy_version,
        icao_hex=normalized,
        evaluated_at=now,
        reasons=assessment.reasons,
        components=_components(pair, window, corroboration, station, now),
    )
    return response, assessment


def _latest_pair(db: Session, icao_hex: str) -> KinematicEvaluationRecord | None:
    return (
        db.query(KinematicEvaluationRecord)
        .filter(KinematicEvaluationRecord.icao_hex == icao_hex)
        .order_by(KinematicEvaluationRecord.evaluated_at.desc())
        .first()
    )


def _latest_window(
    db: Session, icao_hex: str
) -> WindowKinematicEvaluationRecord | None:
    return (
        db.query(WindowKinematicEvaluationRecord)
        .filter(WindowKinematicEvaluationRecord.icao_hex == icao_hex)
        .order_by(WindowKinematicEvaluationRecord.evaluated_at.desc())
        .first()
    )


def _latest_local_observation(
    db: Session, icao_hex: str
) -> TrackObservationRecord | None:
    return (
        db.query(TrackObservationRecord)
        .filter(
            TrackObservationRecord.icao_hex == icao_hex,
            TrackObservationRecord.source_type != "EXTERNAL_FEED",
        )
        .order_by(TrackObservationRecord.observed_at.desc())
        .first()
    )


def _station_record(db: Session, source_id: str | None) -> SensorNodeRecord | None:
    if source_id is None:
        return None
    return (
        db.query(SensorNodeRecord)
        .filter(SensorNodeRecord.node_id == source_id)
        .first()
    )


async def _corroborate(
    local: TrackObservationRecord | None,
    evaluated_at: datetime,
    service: CorroborationService,
) -> CorroborationResult | None:
    if local is None:
        return None
    observation = record_to_observation(local)
    if get_settings().opensky_enabled:
        return await service.corroborate(observation)
    return compare_observations(
        local=observation,
        external=None,
        evaluated_at=evaluated_at,
        source_available=False,
    )


def _components(
    pair: KinematicEvaluationRecord | None,
    window: WindowKinematicEvaluationRecord | None,
    corroboration: CorroborationResult | None,
    station: StationHealthResult | None,
    now: datetime,
) -> tuple[TrustComponentResponse, ...]:
    return (
        _kinematic_component("PAIR_KINEMATICS", pair, now),
        _kinematic_component("WINDOW_KINEMATICS", window, now),
        _corroboration_component(corroboration, now),
        _station_component(station, now),
        TrustComponentResponse(
            component="ML",
            state="NOT_PROMOTED",
            policy_version=None,
            evaluated_at=None,
            age_seconds=None,
            evidence_ids=(),
            reasons=("The learned model remains an offline candidate and does not affect this state.",),
        ),
    )


def _kinematic_component(
    name: Literal["PAIR_KINEMATICS", "WINDOW_KINEMATICS"],
    record: KinematicEvaluationRecord | WindowKinematicEvaluationRecord | None,
    now: datetime,
) -> TrustComponentResponse:
    if record is None:
        return TrustComponentResponse(
            component=name,
            state="NOT_EVALUATED",
            policy_version=None,
            evaluated_at=None,
            age_seconds=None,
            evidence_ids=(),
            reasons=("No persisted evaluation is available.",),
        )
    evaluated_at = _as_utc(record.evaluated_at)
    return TrustComponentResponse(
        component=name,
        state=record.status,
        policy_version=record.policy_version,
        evaluated_at=evaluated_at,
        age_seconds=_age(evaluated_at, now),
        evidence_ids=(str(record.evaluation_id),),
        reasons=(record.reason or "The persisted evaluation produced this state.",),
    )


def _corroboration_component(
    result: CorroborationResult | None, now: datetime
) -> TrustComponentResponse:
    if result is None:
        return TrustComponentResponse(
            component="CORROBORATION",
            state="NOT_EVALUATED",
            policy_version=None,
            evaluated_at=None,
            age_seconds=None,
            evidence_ids=(),
            reasons=("No local observation was available for corroboration.",),
        )
    evidence_ids = tuple(
        value
        for value in (result.local_observation_id, result.external_observation_id)
        if value
    )
    return TrustComponentResponse(
        component="CORROBORATION",
        state=result.state.value,
        policy_version=result.policy_version,
        evaluated_at=result.evaluated_at,
        age_seconds=_age(result.evaluated_at, now),
        evidence_ids=evidence_ids,
        reasons=(result.explanation,),
    )


def _station_component(
    result: StationHealthResult | None, now: datetime
) -> TrustComponentResponse:
    if result is None:
        return TrustComponentResponse(
            component="STATION",
            state="NOT_ASSOCIATED",
            policy_version=None,
            evaluated_at=None,
            age_seconds=None,
            evidence_ids=(),
            reasons=("The observation source is not associated with a monitored station.",),
        )
    evidence_ids = tuple(
        value
        for value in (result.telemetry_message_id, result.presence_message_id)
        if value
    )
    return TrustComponentResponse(
        component="STATION",
        state=result.state.value,
        policy_version=result.policy_version,
        evaluated_at=result.evaluated_at,
        age_seconds=result.telemetry_age_seconds,
        evidence_ids=evidence_ids,
        reasons=result.reasons,
    )


def _normalize_icao(value: str) -> str:
    normalized = value.strip().upper()
    if len(normalized) != 6 or any(
        character not in "0123456789ABCDEF" for character in normalized
    ):
        raise HTTPException(
            status_code=422, detail="ICAO address must be six hexadecimal characters"
        )
    return normalized


def _age(value: datetime, now: datetime) -> float:
    return max(0.0, round((now - _as_utc(value)).total_seconds(), 3))


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
