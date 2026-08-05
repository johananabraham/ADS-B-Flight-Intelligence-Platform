"""Versioned contracts for ESP32 edge-station telemetry and presence."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


NODE_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,62}$"
FIRMWARE_VERSION_PATTERN = r"^[0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?$"


class PresenceStatus(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class StationTelemetry(BaseModel):
    """One immutable station heartbeat; schema 1.0 is firmware/API stable."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    message_id: UUID = Field(default_factory=uuid4)
    node_id: str = Field(pattern=NODE_ID_PATTERN)
    firmware_version: str = Field(pattern=FIRMWARE_VERSION_PATTERN)
    boot_id: UUID
    sequence: int = Field(ge=0)
    observed_at: datetime
    uptime_seconds: int = Field(ge=0)
    reconnect_count: int = Field(ge=0)
    rssi_dbm: int = Field(ge=-127, le=0)
    free_heap_bytes: int = Field(ge=0)
    offline_queue_depth: int = Field(ge=0, le=1_000)
    watchdog_reset_count: int = Field(default=0, ge=0)
    temperature_c: float | None = Field(default=None, ge=-55, le=150)
    supply_voltage_v: float | None = Field(default=None, ge=0, le=24)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class StationPresence(BaseModel):
    """Retained MQTT presence message, including the broker last-will payload."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"] = "1.0"
    message_id: UUID = Field(default_factory=uuid4)
    node_id: str = Field(pattern=NODE_ID_PATTERN)
    status: PresenceStatus
    observed_at: datetime
    reason: str = Field(min_length=1, max_length=100)

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


def telemetry_topic(node_id: str) -> str:
    validated = _validated_node_id(node_id)
    return f"adsb/stations/v1/{validated}/telemetry"


def presence_topic(node_id: str) -> str:
    validated = _validated_node_id(node_id)
    return f"adsb/stations/v1/{validated}/presence"


def node_id_from_topic(topic: str, kind: Literal["telemetry", "presence"]) -> str:
    parts = topic.split("/")
    if len(parts) != 5 or parts[:3] != ["adsb", "stations", "v1"] or parts[4] != kind:
        raise ValueError(f"invalid station {kind} topic")
    return _validated_node_id(parts[3])


def _validated_node_id(node_id: str) -> str:
    return StationPresence(
        node_id=node_id,
        status=PresenceStatus.ONLINE,
        observed_at=datetime.now().astimezone(),
        reason="validation",
    ).node_id
