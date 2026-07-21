from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from sqlalchemy import and_
from datetime import datetime, timedelta
import asyncio

from ..core.database import SessionLocal
from ..models import Aircraft, Anomaly, AnomalySeverity

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                pass


manager = ConnectionManager()


def get_aircraft_data(db: Session) -> list[dict]:
    """Get current aircraft data."""
    cutoff = datetime.utcnow() - timedelta(minutes=5)
    aircraft = db.query(Aircraft).filter(Aircraft.last_seen >= cutoff).all()

    return [
        {
            "icao_hex": a.icao_hex,
            "callsign": a.callsign,
            "latitude": a.latitude,
            "longitude": a.longitude,
            "altitude": a.altitude,
            "ground_speed": a.ground_speed,
            "track": a.track,
            "vertical_rate": a.vertical_rate,
            "squawk": a.squawk,
            "last_seen": a.last_seen.isoformat() if a.last_seen else None,
            "first_seen": a.first_seen.isoformat() if a.first_seen else None,
            "messages_received": a.messages_received,
        }
        for a in aircraft
    ]


def get_stats(db: Session) -> dict:
    """Get current stats."""
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    five_min_ago = now - timedelta(minutes=5)

    from ..models import AircraftPosition

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

    return {
        "active_aircraft": active_aircraft,
        "total_positions_today": total_positions,
        "anomalies_today": anomalies_today,
        "critical_anomalies": critical_anomalies,
        "last_updated": now.isoformat(),
    }


@router.websocket("/ws/aircraft")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            db = SessionLocal()
            try:
                aircraft = get_aircraft_data(db)
                stats = get_stats(db)

                await websocket.send_json({
                    "type": "update",
                    "aircraft": aircraft,
                    "stats": stats,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            finally:
                db.close()

            await asyncio.sleep(1)  # Update every second
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
