from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, timedelta

from ..core.database import get_db
from ..models import Anomaly, AnomalyCategory, AnomalySeverity, AnomalyType
from ..models.user import User
from ..schemas import AnomalyResponse, AnomalyAcknowledge
from ..auth.audit import record_audit_event
from ..auth.dependencies import require_operator

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


@router.get("/", response_model=List[AnomalyResponse])
def get_anomalies(
    anomaly_type: Optional[AnomalyType] = None,
    severity: Optional[AnomalySeverity] = None,
    category: Optional[AnomalyCategory] = None,
    hours: int = Query(default=24, description="Anomalies from last N hours"),
    limit: int = Query(default=100, le=500),
    unacknowledged_only: bool = False,
    db: Session = Depends(get_db),
):
    """Get recent anomalies with optional filters."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    query = db.query(Anomaly).filter(Anomaly.detected_at >= cutoff)

    if anomaly_type:
        query = query.filter(Anomaly.anomaly_type == anomaly_type)

    if severity:
        query = query.filter(Anomaly.severity == severity)

    if category:
        query = query.filter(Anomaly.category == category)

    if unacknowledged_only:
        query = query.filter(Anomaly.acknowledged == 0)

    return query.order_by(Anomaly.detected_at.desc()).limit(limit).all()


@router.get("/critical", response_model=List[AnomalyResponse])
def get_critical_anomalies(
    hours: int = Query(default=24),
    db: Session = Depends(get_db),
):
    """Get critical and high severity anomalies."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    return (
        db.query(Anomaly)
        .filter(
            and_(
                Anomaly.detected_at >= cutoff,
                Anomaly.severity.in_([AnomalySeverity.CRITICAL, AnomalySeverity.HIGH]),
            )
        )
        .order_by(Anomaly.detected_at.desc())
        .all()
    )


@router.get("/squawk", response_model=List[AnomalyResponse])
def get_squawk_anomalies(
    hours: int = Query(default=24),
    db: Session = Depends(get_db),
):
    """Get squawk code anomalies (7500, 7600, 7700)."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    return (
        db.query(Anomaly)
        .filter(
            and_(
                Anomaly.detected_at >= cutoff,
                Anomaly.anomaly_type.in_(
                    [
                        AnomalyType.SQUAWK_7500,
                        AnomalyType.SQUAWK_7600,
                        AnomalyType.SQUAWK_7700,
                    ]
                ),
            )
        )
        .order_by(Anomaly.detected_at.desc())
        .all()
    )


@router.get("/{anomaly_id}", response_model=AnomalyResponse)
def get_anomaly(anomaly_id: int, db: Session = Depends(get_db)):
    """Get a specific anomaly by ID."""
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return anomaly


@router.patch("/{anomaly_id}/acknowledge", response_model=AnomalyResponse)
def acknowledge_anomaly(
    anomaly_id: int,
    ack: AnomalyAcknowledge,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    """Acknowledge or dismiss an anomaly."""
    anomaly = db.query(Anomaly).filter(Anomaly.id == anomaly_id).first()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")

    anomaly.acknowledged = ack.acknowledged
    if ack.acknowledged > 0 and anomaly.resolved_at is None:
        anomaly.resolved_at = datetime.utcnow()

    record_audit_event(
        db,
        event_type="anomaly.acknowledged",
        success=True,
        actor_user_id=current_user.id,
        target_type="anomaly",
        target_id=str(anomaly.id),
        details={"acknowledged": ack.acknowledged},
    )
    db.commit()
    db.refresh(anomaly)
    return anomaly


@router.get("/stats/by-type")
def get_anomaly_stats_by_type(
    hours: int = Query(default=24),
    db: Session = Depends(get_db),
):
    """Get anomaly counts grouped by type."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    from sqlalchemy import func

    results = (
        db.query(Anomaly.anomaly_type, func.count(Anomaly.id))
        .filter(Anomaly.detected_at >= cutoff)
        .group_by(Anomaly.anomaly_type)
        .all()
    )

    return {str(anomaly_type.value): count for anomaly_type, count in results}


@router.get("/stats/by-severity")
def get_anomaly_stats_by_severity(
    hours: int = Query(default=24),
    db: Session = Depends(get_db),
):
    """Get anomaly counts grouped by severity."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    from sqlalchemy import func

    results = (
        db.query(Anomaly.severity, func.count(Anomaly.id))
        .filter(Anomaly.detected_at >= cutoff)
        .group_by(Anomaly.severity)
        .all()
    )

    return {str(severity.value): count for severity, count in results}
