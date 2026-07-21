"""Idempotent persistence for immutable aircraft observations."""

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..models.observation import TrackObservationRecord
from ..schemas.observation import TrackObservation


def observation_values(observation: TrackObservation) -> dict:
    """Flatten the versioned contract into database column values."""
    provenance = observation.provenance
    return {
        "observation_id": observation.observation_id,
        "schema_version": observation.schema_version,
        "source_type": provenance.source_type.value,
        "source_id": provenance.source_id,
        "receiver_id": provenance.receiver_id,
        "recording_id": provenance.recording_id,
        "provider": provenance.provider,
        "license_id": provenance.license_id,
        "icao_hex": observation.icao_hex,
        "observed_at": observation.observed_at,
        "received_at": observation.received_at,
        "callsign": observation.callsign,
        "latitude": observation.latitude,
        "longitude": observation.longitude,
        "altitude_ft": observation.altitude_ft,
        "ground_speed_knots": observation.ground_speed_knots,
        "track_degrees": observation.track_degrees,
        "vertical_rate_fpm": observation.vertical_rate_fpm,
        "squawk": observation.squawk,
        "quality_flags": sorted(flag.value for flag in observation.quality_flags),
        "raw_message_id": observation.raw_message_id,
    }


def build_insert_observation_statement(observation: TrackObservation):
    """Build a PostgreSQL insert that safely ignores replayed observations."""
    return (
        insert(TrackObservationRecord)
        .values(**observation_values(observation))
        .on_conflict_do_nothing(index_elements=["observation_id"])
    )


def insert_observation(db: Session, observation: TrackObservation) -> bool:
    """Insert once; return False when this observation was already stored."""
    result = db.execute(build_insert_observation_statement(observation))
    return result.rowcount == 1
