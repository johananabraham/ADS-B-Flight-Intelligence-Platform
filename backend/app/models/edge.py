"""Persistence models for edge-station current state and immutable events."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class SensorNodeRecord(Base):
    __tablename__ = "sensor_nodes"

    node_id: Mapped[str] = mapped_column(String(63), primary_key=True)
    firmware_version: Mapped[str | None] = mapped_column(String(50))
    boot_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True))
    telemetry_message_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    presence_message_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True)
    )
    last_sequence: Mapped[int | None] = mapped_column(Integer)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    presence_status: Mapped[str | None] = mapped_column(String(20))
    presence_received_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    uptime_seconds: Mapped[int | None] = mapped_column(Integer)
    reconnect_count: Mapped[int | None] = mapped_column(Integer)
    rssi_dbm: Mapped[int | None] = mapped_column(Integer)
    free_heap_bytes: Mapped[int | None] = mapped_column(Integer)
    offline_queue_depth: Mapped[int | None] = mapped_column(Integer)
    watchdog_reset_count: Mapped[int | None] = mapped_column(Integer)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    supply_voltage_v: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (Index("ix_sensor_nodes_last_received", "last_received_at"),)


class StationTelemetryRecord(Base):
    __tablename__ = "station_telemetry"

    message_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False)
    node_id: Mapped[str] = mapped_column(String(63), nullable=False)
    firmware_version: Mapped[str] = mapped_column(String(50), nullable=False)
    boot_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    uptime_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    reconnect_count: Mapped[int] = mapped_column(Integer, nullable=False)
    rssi_dbm: Mapped[int] = mapped_column(Integer, nullable=False)
    free_heap_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    offline_queue_depth: Mapped[int] = mapped_column(Integer, nullable=False)
    watchdog_reset_count: Mapped[int] = mapped_column(Integer, nullable=False)
    temperature_c: Mapped[float | None] = mapped_column(Float)
    supply_voltage_v: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_station_telemetry_node_received", "node_id", "received_at"),
        Index("ix_station_telemetry_boot_sequence", "node_id", "boot_id", "sequence"),
    )


class StationPresenceRecord(Base):
    __tablename__ = "station_presence_events"

    message_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True
    )
    schema_version: Mapped[str] = mapped_column(String(10), nullable=False)
    node_id: Mapped[str] = mapped_column(String(63), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    reason: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (
        Index("ix_station_presence_node_received", "node_id", "received_at"),
    )
