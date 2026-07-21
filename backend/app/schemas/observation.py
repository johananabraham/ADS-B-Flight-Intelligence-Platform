"""Versioned source-observation contract for aircraft tracking."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class ObservationSourceType(str, Enum):
    LIVE_RF = "LIVE_RF"
    SIMULATION = "SIMULATION"
    RECORDED_REPLAY = "RECORDED_REPLAY"
    EXTERNAL_FEED = "EXTERNAL_FEED"


class ObservationQualityFlag(str, Enum):
    CLOCK_SKEW = "CLOCK_SKEW"
    DUPLICATE = "DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    PARTIAL = "PARTIAL"
    STALE = "STALE"
    UNVERIFIED = "UNVERIFIED"


class ObservationProvenance(BaseModel):
    """Identity and licensing context for the system that produced an observation."""

    source_type: ObservationSourceType
    source_id: str = Field(min_length=1, max_length=100)
    receiver_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    recording_id: Optional[str] = Field(default=None, min_length=1, max_length=100)
    provider: Optional[str] = Field(default=None, min_length=1, max_length=100)
    license_id: Optional[str] = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_source_context(self) -> "ObservationProvenance":
        if self.source_type is ObservationSourceType.LIVE_RF and not self.receiver_id:
            raise ValueError("LIVE_RF observations require receiver_id")
        if self.source_type is ObservationSourceType.RECORDED_REPLAY and not self.recording_id:
            raise ValueError("RECORDED_REPLAY observations require recording_id")
        if self.source_type is ObservationSourceType.EXTERNAL_FEED and not self.provider:
            raise ValueError("EXTERNAL_FEED observations require provider")
        return self


class TrackObservation(BaseModel):
    """One immutable report from one source at one observation time."""

    schema_version: Literal["1.0"] = "1.0"
    observation_id: UUID = Field(default_factory=uuid4)
    provenance: ObservationProvenance
    icao_hex: str = Field(pattern=r"^[0-9A-F]{6}$")
    observed_at: datetime
    received_at: datetime

    callsign: Optional[str] = Field(default=None, max_length=8)
    latitude: Optional[float] = Field(default=None, ge=-90, le=90)
    longitude: Optional[float] = Field(default=None, ge=-180, le=180)
    altitude_ft: Optional[int] = Field(default=None, ge=-2_000, le=100_000)
    ground_speed_knots: Optional[float] = Field(default=None, ge=0, le=2_000)
    track_degrees: Optional[float] = Field(default=None, ge=0, lt=360)
    vertical_rate_fpm: Optional[int] = Field(default=None, ge=-20_000, le=20_000)
    squawk: Optional[str] = Field(default=None, pattern=r"^[0-7]{4}$")
    quality_flags: frozenset[ObservationQualityFlag] = Field(default_factory=frozenset)
    raw_message_id: Optional[str] = Field(default=None, max_length=200)

    @field_validator("icao_hex", mode="before")
    @classmethod
    def normalize_icao_hex(cls, value: object) -> object:
        return value.strip().upper() if isinstance(value, str) else value

    @field_validator("callsign", mode="before")
    @classmethod
    def normalize_callsign(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper()
        return normalized or None

    @field_validator("observed_at", "received_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observation timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def require_complete_position(self) -> "TrackObservation":
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be provided together")
        return self

    def timing_quality_flags(
        self,
        *,
        reference_time: datetime,
        previous_observed_at: Optional[datetime] = None,
        stale_after_seconds: float = 30,
        clock_skew_tolerance_seconds: float = 2,
    ) -> frozenset[ObservationQualityFlag]:
        """Classify timing evidence without discarding the observation."""
        if reference_time.tzinfo is None or reference_time.utcoffset() is None:
            raise ValueError("reference_time must include a timezone")
        if previous_observed_at is not None and (
            previous_observed_at.tzinfo is None or previous_observed_at.utcoffset() is None
        ):
            raise ValueError("previous_observed_at must include a timezone")
        if stale_after_seconds < 0 or clock_skew_tolerance_seconds < 0:
            raise ValueError("timing tolerances cannot be negative")

        flags = set(self.quality_flags)
        if (reference_time - self.observed_at).total_seconds() > stale_after_seconds:
            flags.add(ObservationQualityFlag.STALE)
        if (self.observed_at - self.received_at).total_seconds() > clock_skew_tolerance_seconds:
            flags.add(ObservationQualityFlag.CLOCK_SKEW)
        if previous_observed_at is not None and self.observed_at <= previous_observed_at:
            flags.add(ObservationQualityFlag.OUT_OF_ORDER)
        return frozenset(flags)
