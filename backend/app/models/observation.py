"""Persistence model for immutable source observations."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class TrackObservationRecord(Base):
    """One append-only report received from one aircraft data source."""

    __tablename__ = "track_observations"

    observation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    receiver_id: Mapped[str | None] = mapped_column(String(100))
    recording_id: Mapped[str | None] = mapped_column(String(100))
    provider: Mapped[str | None] = mapped_column(String(100))
    license_id: Mapped[str | None] = mapped_column(String(100))

    icao_hex: Mapped[str] = mapped_column(String(6), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    callsign: Mapped[str | None] = mapped_column(String(8))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    altitude_ft: Mapped[int | None] = mapped_column(Integer)
    ground_speed_knots: Mapped[float | None] = mapped_column(Float)
    track_degrees: Mapped[float | None] = mapped_column(Float)
    vertical_rate_fpm: Mapped[int | None] = mapped_column(Integer)
    squawk: Mapped[str | None] = mapped_column(String(4))
    quality_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    raw_message_id: Mapped[str | None] = mapped_column(String(200))

    __table_args__ = (
        Index("ix_track_observations_icao_time", "icao_hex", "observed_at"),
        Index("ix_track_observations_source_time", "source_id", "observed_at"),
    )
