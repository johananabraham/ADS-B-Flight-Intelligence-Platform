from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from ..models.aircraft import AnomalyType, AnomalySeverity


class AircraftBase(BaseModel):
    icao_hex: str
    callsign: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[int] = None
    ground_speed: Optional[float] = None
    track: Optional[float] = None
    vertical_rate: Optional[int] = None
    squawk: Optional[str] = None


class AircraftCreate(AircraftBase):
    pass


class AircraftResponse(AircraftBase):
    id: int
    last_seen: datetime
    first_seen: datetime
    messages_received: int

    class Config:
        from_attributes = True


class AircraftPositionResponse(BaseModel):
    icao_hex: str
    latitude: float
    longitude: float
    altitude: Optional[int] = None
    ground_speed: Optional[float] = None
    track: Optional[float] = None
    timestamp: datetime

    class Config:
        from_attributes = True


class FlightTrailResponse(BaseModel):
    icao_hex: str
    callsign: Optional[str] = None
    positions: List[AircraftPositionResponse]


class AnomalyResponse(BaseModel):
    id: int
    icao_hex: str
    callsign: Optional[str] = None
    anomaly_type: AnomalyType
    severity: AnomalySeverity
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[int] = None
    description: Optional[str] = None
    details: Optional[dict] = None
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    acknowledged: int

    class Config:
        from_attributes = True


class AnomalyAcknowledge(BaseModel):
    acknowledged: int  # 0=new, 1=acknowledged, 2=dismissed


class DailySummaryResponse(BaseModel):
    id: int
    date: datetime
    total_aircraft: int
    total_positions: int
    total_anomalies: int
    summary_text: Optional[str] = None
    key_events: Optional[dict] = None
    generated_at: datetime

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    active_aircraft: int
    total_positions_today: int
    anomalies_today: int
    critical_anomalies: int
    last_updated: datetime


class BoundsRequest(BaseModel):
    min_lat: float
    max_lat: float
    min_lon: float
    max_lon: float
