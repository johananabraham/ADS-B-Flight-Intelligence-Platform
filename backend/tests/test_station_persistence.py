"""Persistence and MQTT boundary tests for edge-station telemetry."""

import json
from datetime import datetime, timezone
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from app.schemas.edge import (
    PresenceStatus,
    ReceiverConnection,
    ReceiverPipelineTelemetry,
    StationPresence,
    StationTelemetry,
)
from app.services import station_mqtt
from app.services.station_mqtt import StationMessageError, process_station_message
from app.services.station_persistence import (
    build_presence_event_insert,
    build_presence_node_upsert,
    build_pipeline_event_insert,
    build_pipeline_node_upsert,
    build_telemetry_event_insert,
    build_telemetry_node_upsert,
    persist_presence,
    persist_pipeline,
    persist_telemetry,
)


NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)


def telemetry() -> StationTelemetry:
    return StationTelemetry(
        message_id=UUID("00000000-0000-4000-8000-000000000010"),
        node_id="roof-node-1",
        firmware_version="1.0.0",
        boot_id=UUID("00000000-0000-4000-8000-000000000001"),
        sequence=42,
        observed_at=NOW,
        uptime_seconds=300,
        reconnect_count=1,
        rssi_dbm=-60,
        free_heap_bytes=100_000,
        offline_queue_depth=0,
    )


def presence(status: PresenceStatus = PresenceStatus.ONLINE) -> StationPresence:
    return StationPresence(
        message_id=UUID("00000000-0000-4000-8000-000000000020"),
        node_id="roof-node-1",
        status=status,
        observed_at=NOW,
        reason="connected" if status is PresenceStatus.ONLINE else "mqtt-last-will",
    )


def pipeline() -> ReceiverPipelineTelemetry:
    return ReceiverPipelineTelemetry(
        message_id=UUID("00000000-0000-4000-8000-000000000030"),
        node_id="roof-node-1",
        observed_at=NOW,
        connection=ReceiverConnection.CONNECTED,
        policy_version="feeder-v1",
        last_message_age_seconds=2,
        queue_depth=0,
        queue_capacity=128,
        dropped_messages_total=0,
        reconnects_total=1,
    )


def compiled(statement) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_event_inserts_ignore_duplicate_message_or_boot_sequence():
    telemetry_sql = compiled(build_telemetry_event_insert(telemetry(), NOW))
    presence_sql = compiled(build_presence_event_insert(presence(), NOW))
    pipeline_sql = compiled(build_pipeline_event_insert(pipeline(), NOW))

    assert "ON CONFLICT DO NOTHING" in telemetry_sql
    assert "ON CONFLICT DO NOTHING" in presence_sql
    assert "ON CONFLICT DO NOTHING" in pipeline_sql


def test_current_state_upserts_only_newer_backend_receipts():
    telemetry_sql = compiled(build_telemetry_node_upsert(telemetry(), NOW))
    presence_sql = compiled(build_presence_node_upsert(presence(), NOW))
    pipeline_sql = compiled(build_pipeline_node_upsert(pipeline(), NOW))

    assert "ON CONFLICT (node_id) DO UPDATE" in telemetry_sql
    assert "excluded.last_received_at > sensor_nodes.last_received_at" in telemetry_sql
    assert "sensor_nodes.presence_received_at IS NULL" in presence_sql
    assert "sensor_nodes.pipeline_received_at IS NULL" in pipeline_sql


def test_persistence_reports_idempotent_event_insertion():
    db = Mock()
    db.execute.side_effect = [Mock(rowcount=1), Mock(rowcount=1)]
    assert persist_telemetry(db, telemetry(), NOW) is True
    assert db.execute.call_count == 2

    db.reset_mock()
    db.execute.side_effect = [Mock(rowcount=0), Mock(rowcount=0)]
    assert persist_presence(db, presence(), NOW) is False

    db.reset_mock()
    db.execute.side_effect = [Mock(rowcount=1), Mock(rowcount=1)]
    assert persist_pipeline(db, pipeline(), NOW) is True


def test_received_time_must_be_timezone_aware():
    with pytest.raises(ValueError, match="timezone"):
        build_telemetry_event_insert(telemetry(), datetime(2026, 8, 4, 12))


def test_mqtt_boundary_validates_topic_identity_and_persists(monkeypatch):
    captured = {}

    def fake_persist(_db, message, received_at):
        captured.update(message=message, received_at=received_at)
        return True

    monkeypatch.setattr(station_mqtt, "persist_telemetry", fake_persist)
    result = process_station_message(
        Mock(),
        topic="adsb/stations/v1/roof-node-1/telemetry",
        payload=telemetry().model_dump_json().encode(),
        received_at=NOW,
    )

    assert result.inserted is True
    assert result.node_id == "roof-node-1"
    assert captured["message"].sequence == 42


def test_last_will_uses_broker_receive_time(monkeypatch):
    captured = {}

    def fake_persist(_db, message, _received_at):
        captured["message"] = message
        return True

    monkeypatch.setattr(station_mqtt, "persist_presence", fake_persist)
    payload = presence(PresenceStatus.OFFLINE).model_dump_json().encode()
    received_at = datetime(2026, 8, 4, 12, 5, tzinfo=timezone.utc)
    process_station_message(
        Mock(),
        topic="adsb/stations/v1/roof-node-1/presence",
        payload=payload,
        received_at=received_at,
    )

    assert captured["message"].observed_at == received_at


def test_mqtt_boundary_validates_and_persists_pipeline(monkeypatch):
    captured = {}

    def fake_persist(_db, message, received_at):
        captured.update(message=message, received_at=received_at)
        return True

    monkeypatch.setattr(station_mqtt, "persist_pipeline", fake_persist)
    result = process_station_message(
        Mock(),
        topic="adsb/stations/v1/roof-node-1/pipeline",
        payload=pipeline().model_dump_json().encode(),
        received_at=NOW,
    )
    assert result.kind == "pipeline"
    assert result.inserted is True
    assert captured["message"].connection is ReceiverConnection.CONNECTED


@pytest.mark.parametrize(
    ("topic", "payload", "reason"),
    [
        (
            "adsb/stations/v1/other-node/telemetry",
            telemetry().model_dump_json().encode(),
            "does not match",
        ),
        ("adsb/stations/v1/roof-node-1/unknown", b"{}", "unsupported"),
        ("adsb/stations/v1/roof-node-1/telemetry", b"not-json", "UTF-8 JSON"),
        (
            "adsb/stations/v1/roof-node-1/telemetry",
            json.dumps([]).encode(),
            "JSON object",
        ),
        ("adsb/stations/v1/roof-node-1/telemetry", b"x" * 4_097, "4096"),
    ],
)
def test_mqtt_boundary_rejects_untrusted_messages(topic, payload, reason):
    with pytest.raises(StationMessageError, match=reason):
        process_station_message(Mock(), topic=topic, payload=payload, received_at=NOW)
