"""Adapters from source-specific payloads to the shared observation contract."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import NAMESPACE_URL, uuid5

from ..schemas.observation import (
    ObservationProvenance,
    ObservationQualityFlag,
    ObservationSourceType,
    TrackObservation,
)


def sbs_state_to_observation(
    data: dict[str, Any],
    *,
    source_type: ObservationSourceType,
    source_id: str,
    observed_at: datetime,
    received_at: datetime,
    receiver_id: Optional[str] = None,
    recording_id: Optional[str] = None,
    raw_message_id: Optional[str] = None,
) -> TrackObservation:
    """Map the ingestion service's parsed SBS field names to version 1.0."""
    has_complete_position = data.get("lat") is not None and data.get("lon") is not None
    quality_flags = frozenset() if has_complete_position else frozenset(
        {ObservationQualityFlag.PARTIAL}
    )
    identity = (
        {
            "observation_id": uuid5(
                NAMESPACE_URL,
                f"adsb:{source_type.value}:{source_id}:{raw_message_id}",
            )
        }
        if raw_message_id
        else {}
    )

    return TrackObservation(
        **identity,
        provenance=ObservationProvenance(
            source_type=source_type,
            source_id=source_id,
            receiver_id=receiver_id,
            recording_id=recording_id,
        ),
        icao_hex=data.get("hex"),
        observed_at=observed_at,
        received_at=received_at,
        callsign=data.get("flight"),
        latitude=data.get("lat"),
        longitude=data.get("lon"),
        altitude_ft=data.get("altitude"),
        ground_speed_knots=data.get("gs"),
        track_degrees=data.get("track"),
        vertical_rate_fpm=data.get("vert_rate"),
        squawk=data.get("squawk"),
        quality_flags=quality_flags,
        raw_message_id=raw_message_id,
    )
