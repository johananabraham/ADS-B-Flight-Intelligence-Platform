"""Tests for immutable, idempotent observation persistence."""

from datetime import datetime, timezone
from unittest.mock import Mock

from sqlalchemy.dialects import postgresql

from app.schemas.observation import ObservationSourceType
from app.services.observation_adapters import sbs_state_to_observation
from app.services.observation_persistence import (
    build_insert_observation_statement,
    insert_observation,
    observation_values,
)


NOW = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)


def build_observation(raw_message_id: str = "message-42"):
    return sbs_state_to_observation(
        {"hex": "A1B2C3", "lat": 39.96, "lon": -82.99},
        source_type=ObservationSourceType.SIMULATION,
        source_id="columbus-demo",
        observed_at=NOW,
        received_at=NOW,
        raw_message_id=raw_message_id,
    )


def test_raw_message_identity_is_deterministic_per_source() -> None:
    first = build_observation()
    retry = build_observation()
    different_message = build_observation("message-43")

    assert first.observation_id == retry.observation_id
    assert first.observation_id != different_message.observation_id


def test_source_type_is_part_of_observation_identity() -> None:
    simulation = build_observation()
    replay = sbs_state_to_observation(
        {"hex": "A1B2C3", "lat": 39.96, "lon": -82.99},
        source_type=ObservationSourceType.RECORDED_REPLAY,
        source_id="columbus-demo",
        recording_id="demo-recording",
        observed_at=NOW,
        received_at=NOW,
        raw_message_id="message-42",
    )

    assert simulation.observation_id != replay.observation_id


def test_flattens_contract_without_losing_provenance() -> None:
    values = observation_values(build_observation())

    assert values["source_type"] == "SIMULATION"
    assert values["source_id"] == "columbus-demo"
    assert values["icao_hex"] == "A1B2C3"
    assert values["quality_flags"] == []
    assert values["raw_message_id"] == "message-42"


def test_insert_statement_ignores_duplicate_observation_id() -> None:
    statement = build_insert_observation_statement(build_observation())
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "ON CONFLICT (observation_id) DO NOTHING" in sql


def test_insert_reports_whether_database_added_the_row() -> None:
    db = Mock()
    db.execute.side_effect = [Mock(rowcount=1), Mock(rowcount=0)]
    observation = build_observation()

    assert insert_observation(db, observation) is True
    assert insert_observation(db, observation) is False
