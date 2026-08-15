from sqlalchemy import Column, Integer, String, Float, DateTime, Index, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from geoalchemy2 import Geometry
from datetime import datetime
import enum

from ..core.database import Base


class Aircraft(Base):
    """Current state of tracked aircraft."""
    __tablename__ = "aircraft"

    id = Column(Integer, primary_key=True, index=True)
    icao_hex = Column(String(6), unique=True, index=True, nullable=False)
    callsign = Column(String(8), nullable=True)
    registration = Column(String(10), nullable=True)
    aircraft_type = Column(String(10), nullable=True)

    # Current position
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    position = Column(Geometry("POINT", srid=4326), nullable=True)

    # Flight data
    altitude = Column(Integer, nullable=True)  # feet
    ground_speed = Column(Float, nullable=True)  # knots
    track = Column(Float, nullable=True)  # degrees
    vertical_rate = Column(Integer, nullable=True)  # ft/min
    squawk = Column(String(4), nullable=True)

    # Timestamps
    last_seen = Column(DateTime, default=datetime.utcnow, index=True)
    first_seen = Column(DateTime, default=datetime.utcnow)

    # Metadata
    messages_received = Column(Integer, default=0)

    __table_args__ = (
        Index("ix_aircraft_position", position, postgresql_using="gist"),
        Index("ix_aircraft_last_seen_icao", "last_seen", "icao_hex"),
    )


class AircraftPosition(Base):
    """Historical position records for flight trails."""
    __tablename__ = "aircraft_positions"

    id = Column(Integer, primary_key=True, index=True)
    icao_hex = Column(String(6), index=True, nullable=False)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    position = Column(Geometry("POINT", srid=4326), nullable=True)

    altitude = Column(Integer, nullable=True)
    ground_speed = Column(Float, nullable=True)
    track = Column(Float, nullable=True)
    vertical_rate = Column(Integer, nullable=True)

    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_positions_icao_time", "icao_hex", "timestamp"),
        Index("ix_positions_time", "timestamp"),
    )


class AnomalyType(str, enum.Enum):
    RAPID_DESCENT = "RAPID_DESCENT"
    RAPID_CLIMB = "RAPID_CLIMB"
    SPEED_ANOMALY = "SPEED_ANOMALY"
    SQUAWK_7500 = "SQUAWK_7500"  # Hijack
    SQUAWK_7600 = "SQUAWK_7600"  # Radio failure
    SQUAWK_7700 = "SQUAWK_7700"  # Emergency
    TRACK_LOSS = "TRACK_LOSS"
    GHOST_FLIGHT = "GHOST_FLIGHT"  # Legacy persisted value; never emit for live data.
    RESTRICTED_AIRSPACE = "RESTRICTED_AIRSPACE"
    ALTITUDE_DEVIATION = "ALTITUDE_DEVIATION"
    KINEMATIC_PLAUSIBILITY = "KINEMATIC_PLAUSIBILITY"


class AnomalySeverity(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AnomalyCategory(str, enum.Enum):
    OPERATIONAL_EVENT = "OPERATIONAL_EVENT"
    INTEGRITY_EVIDENCE = "INTEGRITY_EVIDENCE"


class Anomaly(Base):
    """Detected anomalies in flight behavior."""
    __tablename__ = "anomalies"

    id = Column(Integer, primary_key=True, index=True)
    icao_hex = Column(String(6), index=True, nullable=False)
    callsign = Column(String(8), nullable=True)

    anomaly_type = Column(SQLEnum(AnomalyType), nullable=False)
    severity = Column(SQLEnum(AnomalySeverity), nullable=False)
    category = Column(
        SQLEnum(
            AnomalyCategory,
            values_callable=lambda enum_type: [item.value for item in enum_type],
            native_enum=False,
            length=32,
        ),
        default=AnomalyCategory.OPERATIONAL_EVENT,
        nullable=False,
    )

    # Position at time of anomaly
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    altitude = Column(Integer, nullable=True)

    # Anomaly details
    description = Column(String(500), nullable=True)
    details = Column(JSONB, nullable=True)  # Additional context

    # Timing
    detected_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at = Column(DateTime, nullable=True)

    # Status
    acknowledged = Column(Integer, default=0)  # 0=new, 1=acknowledged, 2=dismissed

    __table_args__ = (
        Index("ix_anomalies_type_time", "anomaly_type", "detected_at"),
    )


class DailySummary(Base):
    """AI-generated daily intelligence summaries."""
    __tablename__ = "daily_summaries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(DateTime, unique=True, index=True, nullable=False)

    # Stats
    total_aircraft = Column(Integer, default=0)
    total_positions = Column(Integer, default=0)
    total_anomalies = Column(Integer, default=0)

    # AI-generated content
    summary_text = Column(String(5000), nullable=True)
    key_events = Column(JSONB, nullable=True)

    generated_at = Column(DateTime, default=datetime.utcnow)
