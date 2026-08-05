from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.edge import (
    PresenceStatus,
    StationPresence,
    StationTelemetry,
    node_id_from_topic,
    presence_topic,
    telemetry_topic,
)
from app.services.station_health import StationHealthState, evaluate_station_health


NOW = datetime(2026, 8, 4, 12, tzinfo=timezone.utc)


def telemetry(**updates) -> StationTelemetry:
    values = {
        "node_id": "roof-node-1",
        "firmware_version": "1.0.0",
        "boot_id": UUID("00000000-0000-4000-8000-000000000001"),
        "sequence": 10,
        "observed_at": NOW,
        "uptime_seconds": 3_600,
        "reconnect_count": 1,
        "rssi_dbm": -60,
        "free_heap_bytes": 100_000,
        "offline_queue_depth": 0,
    }
    values.update(updates)
    return StationTelemetry(**values)


def presence(status: PresenceStatus, **updates) -> StationPresence:
    values = {
        "node_id": "roof-node-1",
        "status": status,
        "observed_at": NOW,
        "reason": "connected" if status is PresenceStatus.ONLINE else "mqtt-last-will",
    }
    values.update(updates)
    return StationPresence(**values)


def test_station_contract_rejects_naive_time_and_invalid_node_id():
    with pytest.raises(ValidationError, match="timezone"):
        telemetry(observed_at=datetime(2026, 8, 4, 12))
    with pytest.raises(ValidationError, match="string_pattern_mismatch"):
        telemetry(node_id="../other-node")
    with pytest.raises(ValidationError, match="extra_forbidden"):
        telemetry(unexpected_field="not allowed")


def test_topics_are_versioned_and_reject_wildcard_injection():
    assert telemetry_topic("roof-node-1") == "adsb/stations/v1/roof-node-1/telemetry"
    assert presence_topic("roof-node-1") == "adsb/stations/v1/roof-node-1/presence"
    assert (
        node_id_from_topic("adsb/stations/v1/roof-node-1/telemetry", "telemetry")
        == "roof-node-1"
    )
    with pytest.raises(ValueError):
        telemetry_topic("roof-node-1/#")


def test_fresh_nominal_telemetry_is_healthy():
    result = evaluate_station_health(
        telemetry=telemetry(),
        presence=presence(PresenceStatus.ONLINE),
        evaluated_at=NOW + timedelta(seconds=10),
    )

    assert result.state is StationHealthState.HEALTHY
    assert result.telemetry_age_seconds == 10


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"rssi_dbm": -90}, "RSSI"),
        ({"free_heap_bytes": 40_000}, "heap"),
        ({"offline_queue_depth": 3}, "offline queue"),
        ({"watchdog_reset_count": 1}, "watchdog"),
    ],
)
def test_reported_resource_or_connectivity_evidence_is_degraded(updates, reason):
    result = evaluate_station_health(
        telemetry=telemetry(**updates),
        presence=presence(PresenceStatus.ONLINE),
        evaluated_at=NOW + timedelta(seconds=10),
    )

    assert result.state is StationHealthState.DEGRADED
    assert reason.lower() in " ".join(result.reasons).lower()


def test_missing_heartbeat_becomes_stale():
    result = evaluate_station_health(
        telemetry=telemetry(),
        presence=presence(PresenceStatus.ONLINE),
        evaluated_at=NOW + timedelta(seconds=46),
    )

    assert result.state is StationHealthState.STALE


def test_last_will_is_offline_when_newer_than_telemetry():
    result = evaluate_station_health(
        telemetry=telemetry(),
        presence=presence(
            PresenceStatus.OFFLINE, observed_at=NOW + timedelta(seconds=5)
        ),
        evaluated_at=NOW + timedelta(seconds=10),
    )

    assert result.state is StationHealthState.OFFLINE
    assert "last-will" in result.reasons[0]


def test_online_presence_without_telemetry_is_no_data():
    result = evaluate_station_health(
        telemetry=None,
        presence=presence(PresenceStatus.ONLINE),
        evaluated_at=NOW,
    )

    assert result.state is StationHealthState.NO_DATA


def test_station_sources_must_match():
    with pytest.raises(ValueError, match="same node"):
        evaluate_station_health(
            telemetry=telemetry(),
            presence=presence(PresenceStatus.ONLINE, node_id="other-node"),
            evaluated_at=NOW,
        )
