from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from typing import List, Optional
from datetime import datetime, timedelta

from ..core.database import get_db
from ..models import Aircraft, AircraftPosition, Anomaly, AnomalyType, AnomalySeverity
from ..schemas import (
    AircraftResponse,
    AircraftPositionResponse,
    FlightTrailResponse,
    StatsResponse,
)

router = APIRouter(prefix="/aircraft", tags=["aircraft"])


@router.get("/", response_model=List[AircraftResponse])
def get_active_aircraft(
    min_lat: Optional[float] = None,
    max_lat: Optional[float] = None,
    min_lon: Optional[float] = None,
    max_lon: Optional[float] = None,
    minutes: int = Query(default=5, description="Aircraft seen in last N minutes"),
    db: Session = Depends(get_db),
):
    """Get all currently active aircraft."""
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)

    query = db.query(Aircraft).filter(Aircraft.last_seen >= cutoff)

    # Apply bounding box filter if provided
    if all([min_lat, max_lat, min_lon, max_lon]):
        query = query.filter(
            and_(
                Aircraft.latitude >= min_lat,
                Aircraft.latitude <= max_lat,
                Aircraft.longitude >= min_lon,
                Aircraft.longitude <= max_lon,
            )
        )

    return query.all()


@router.get("/count")
def get_aircraft_count(
    minutes: int = Query(default=5),
    db: Session = Depends(get_db),
):
    """Get count of active aircraft."""
    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    count = db.query(Aircraft).filter(Aircraft.last_seen >= cutoff).count()
    return {"count": count, "minutes": minutes}


@router.get("/{icao_hex}", response_model=AircraftResponse)
def get_aircraft(icao_hex: str, db: Session = Depends(get_db)):
    """Get a specific aircraft by ICAO hex code."""
    aircraft = db.query(Aircraft).filter(Aircraft.icao_hex == icao_hex.upper()).first()
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")
    return aircraft


@router.get("/{icao_hex}/trail", response_model=FlightTrailResponse)
def get_flight_trail(
    icao_hex: str,
    minutes: int = Query(default=30, description="Trail duration in minutes"),
    db: Session = Depends(get_db),
):
    """Get position history for an aircraft."""
    icao_hex = icao_hex.upper()

    aircraft = db.query(Aircraft).filter(Aircraft.icao_hex == icao_hex).first()
    if not aircraft:
        raise HTTPException(status_code=404, detail="Aircraft not found")

    cutoff = datetime.utcnow() - timedelta(minutes=minutes)
    positions = (
        db.query(AircraftPosition)
        .filter(
            and_(
                AircraftPosition.icao_hex == icao_hex,
                AircraftPosition.timestamp >= cutoff,
            )
        )
        .order_by(AircraftPosition.timestamp.asc())
        .all()
    )

    return FlightTrailResponse(
        icao_hex=icao_hex,
        callsign=aircraft.callsign,
        positions=[
            AircraftPositionResponse(
                icao_hex=p.icao_hex,
                latitude=p.latitude,
                longitude=p.longitude,
                altitude=p.altitude,
                ground_speed=p.ground_speed,
                track=p.track,
                timestamp=p.timestamp,
            )
            for p in positions
        ],
    )


@router.get("/stats/overview", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Get current tracking statistics."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    five_min_ago = now - timedelta(minutes=5)

    active_aircraft = (
        db.query(Aircraft).filter(Aircraft.last_seen >= five_min_ago).count()
    )

    total_positions = (
        db.query(AircraftPosition)
        .filter(AircraftPosition.timestamp >= today_start)
        .count()
    )

    anomalies_today = (
        db.query(Anomaly).filter(Anomaly.detected_at >= today_start).count()
    )

    critical_anomalies = (
        db.query(Anomaly)
        .filter(
            and_(
                Anomaly.detected_at >= today_start,
                Anomaly.severity == AnomalySeverity.CRITICAL,
            )
        )
        .count()
    )

    return StatsResponse(
        active_aircraft=active_aircraft,
        total_positions_today=total_positions,
        anomalies_today=anomalies_today,
        critical_anomalies=critical_anomalies,
        last_updated=now,
    )
