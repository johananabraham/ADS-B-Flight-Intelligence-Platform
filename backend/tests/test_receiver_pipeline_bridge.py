from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.edge import ReceiverConnection
from services.edge_telemetry.receiver_bridge import (
    pipeline_from_health,
    unavailable_pipeline,
    validate_sidecar_url,
)


NOW = datetime(2026, 8, 29, 12, tzinfo=timezone.utc)


def health(**updates):
    values = {
        "schema_version": "1.0",
        "connection": "CONNECTED",
        "policy_version": "feeder-v1",
        "last_message_at": (NOW - timedelta(seconds=4)).isoformat(),
        "queue_depth": 2,
        "queue_capacity": 128,
        "dropped_messages_total": 0,
        "reconnects_total": 1,
        "detail": "not forwarded",
        "connected_at": NOW.isoformat(),
    }
    values.update(updates)
    return values


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1:8090",
        "http://192.168.1.5:8090",
        "http://user:pass@127.0.0.1:8090",
        "http://127.0.0.1:8090/api/v1/integrity/health?token=x",
    ],
)
def test_bridge_rejects_non_loopback_or_credential_bearing_sidecar_url(url):
    with pytest.raises(ValueError):
        validate_sidecar_url(url)


def test_bridge_maps_only_aggregate_health_and_computes_message_age():
    message = pipeline_from_health("roof-node-1", health(), observed_at=NOW)
    document = message.model_dump(mode="json")
    assert message.connection is ReceiverConnection.CONNECTED
    assert message.last_message_age_seconds == 4
    assert "detail" not in document
    assert "connected_at" not in document
    assert set(document) == {
        "schema_version",
        "message_id",
        "node_id",
        "observed_at",
        "connection",
        "policy_version",
        "last_message_age_seconds",
        "queue_depth",
        "queue_capacity",
        "dropped_messages_total",
        "reconnects_total",
    }


def test_bridge_fails_closed_for_invalid_or_overfull_health():
    with pytest.raises((ValueError, ValidationError)):
        pipeline_from_health("roof-node-1", health(queue_depth=129), observed_at=NOW)
    unavailable = unavailable_pipeline("roof-node-1", NOW)
    assert unavailable.connection is ReceiverConnection.DISCONNECTED
    assert unavailable.policy_version == "sidecar-unavailable"
