"""Deterministic offline evidence for edge-station health classification."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from ..schemas.edge import (
    PresenceStatus,
    ReceiverConnection,
    ReceiverPipelineTelemetry,
    StationPresence,
    StationTelemetry,
)
from ..services.station_health import (
    StationHealthPolicy,
    StationHealthState,
    evaluate_station_health,
)


EVALUATED_AT = datetime(2026, 8, 4, 12, 0, tzinfo=timezone.utc)
IMPLEMENTATION_PATHS = (
    Path(__file__).parents[1] / "schemas/edge.py",
    Path(__file__).parents[1] / "services/station_health.py",
)


def run_station_health_evaluation(*, implementation_revision: str) -> dict[str, object]:
    scenarios = _scenarios()
    samples = []
    mismatches = []
    state_counts: Counter[str] = Counter()
    for name, expected, telemetry, presence, pipeline in scenarios:
        result = evaluate_station_health(
            telemetry=telemetry,
            presence=presence,
            pipeline=pipeline,
            evaluated_at=EVALUATED_AT,
        )
        state_counts[result.state.value] += 1
        sample = {
            "scenario": name,
            "expected_state": expected.value,
            "actual_state": result.state.value,
            "reasons": list(result.reasons),
        }
        samples.append(sample)
        if result.state is not expected:
            mismatches.append(sample)

    return {
        "suite_version": "1.1-offline-synthetic",
        "evidence_class": "OFFLINE_SYNTHETIC_ONLY",
        "implementation_revision": implementation_revision,
        "implementation_sha256": _implementation_hash(),
        "configuration": {
            "evaluated_at": EVALUATED_AT.isoformat(),
            "scenario_count": len(scenarios),
            "policy_version": StationHealthPolicy().version,
        },
        "results": {
            "exact_match_accuracy": (len(scenarios) - len(mismatches)) / len(scenarios),
            "classification_mismatches": mismatches,
            "state_counts": dict(sorted(state_counts.items())),
            "samples": samples,
        },
        "verification_boundaries": {
            "physical_esp32_sessions": 0,
            "live_mqtt_messages": 0,
            "rf_health_claim_permitted": False,
            "receiver_pipeline_reliability_claim_permitted": False,
            "field_reliability_claim_permitted": False,
            "next_required_evidence": (
                "Run the firmware on the target ESP32, interrupt Wi-Fi and broker "
                "connectivity, and record recovery plus long-duration stability."
            ),
        },
    }


def passes_offline_gate(report: dict[str, object]) -> bool:
    results = report["results"]
    assert isinstance(results, dict)
    return (
        results["exact_match_accuracy"] == 1.0
        and results["classification_mismatches"] == []
    )


def run_receiver_recovery_rehearsal() -> dict[str, object]:
    """Exercise receiver-health policy transitions without claiming field timing."""
    expected_states = (
        StationHealthState.HEALTHY,
        StationHealthState.DEGRADED,
        StationHealthState.STALE,
        StationHealthState.HEALTHY,
    )
    steps = (
        (
            "nominal",
            0,
            _telemetry(),
            _presence(),
            _pipeline(),
        ),
        (
            "receiver_disconnected",
            10,
            _telemetry(observed_at=EVALUATED_AT + timedelta(seconds=5)),
            _presence(observed_at=EVALUATED_AT + timedelta(seconds=5)),
            _pipeline(
                observed_at=EVALUATED_AT + timedelta(seconds=9),
                connection=ReceiverConnection.DISCONNECTED,
            ),
        ),
        (
            "telemetry_timeout",
            60,
            _telemetry(observed_at=EVALUATED_AT + timedelta(seconds=5)),
            _presence(observed_at=EVALUATED_AT + timedelta(seconds=5)),
            _pipeline(
                observed_at=EVALUATED_AT + timedelta(seconds=9),
                connection=ReceiverConnection.DISCONNECTED,
            ),
        ),
        (
            "fresh_telemetry_recovered",
            65,
            _telemetry(observed_at=EVALUATED_AT + timedelta(seconds=64)),
            _presence(observed_at=EVALUATED_AT + timedelta(seconds=64)),
            _pipeline(observed_at=EVALUATED_AT + timedelta(seconds=64)),
        ),
    )

    timeline = []
    for expected, (name, offset, telemetry, presence, pipeline) in zip(
        expected_states, steps, strict=True
    ):
        result = evaluate_station_health(
            telemetry=telemetry,
            presence=presence,
            pipeline=pipeline,
            evaluated_at=EVALUATED_AT + timedelta(seconds=offset),
        )
        timeline.append(
            {
                "step": name,
                "simulated_offset_seconds": offset,
                "expected_state": expected.value,
                "actual_state": result.state.value,
                "reasons": list(result.reasons),
            }
        )

    return {
        "suite_version": "1.0-offline-policy-transition",
        "evidence_class": "OFFLINE_SYNTHETIC_ONLY",
        "policy_version": StationHealthPolicy().version,
        "timeline": timeline,
        "exact_sequence_match": all(
            item["expected_state"] == item["actual_state"] for item in timeline
        ),
        "verification_boundaries": {
            "physical_receiver_disconnects": 0,
            "physical_esp32_sessions": 0,
            "measured_recovery_time_permitted": False,
            "field_reliability_claim_permitted": False,
        },
    }


def passes_receiver_recovery_gate(report: dict[str, object]) -> bool:
    return report.get("exact_sequence_match") is True


def _scenarios() -> (
    list[
        tuple[
            str,
            StationHealthState,
            StationTelemetry | None,
            StationPresence | None,
            ReceiverPipelineTelemetry | None,
        ]
    ]
):
    fresh = _telemetry()
    return [
        ("no_data", StationHealthState.NO_DATA, None, None, None),
        ("fresh_nominal", StationHealthState.HEALTHY, fresh, _presence(), None),
        (
            "weak_wifi",
            StationHealthState.DEGRADED,
            _telemetry(rssi_dbm=-85),
            _presence(),
            None,
        ),
        (
            "offline_backpressure",
            StationHealthState.DEGRADED,
            _telemetry(offline_queue_depth=4),
            _presence(),
            None,
        ),
        (
            "watchdog_recovery",
            StationHealthState.DEGRADED,
            _telemetry(watchdog_reset_count=1),
            _presence(),
            None,
        ),
        (
            "heartbeat_timeout",
            StationHealthState.STALE,
            _telemetry(observed_at=EVALUATED_AT - timedelta(seconds=46)),
            _presence(observed_at=EVALUATED_AT - timedelta(seconds=46)),
            None,
        ),
        (
            "broker_last_will",
            StationHealthState.OFFLINE,
            fresh,
            _presence(
                status=PresenceStatus.OFFLINE,
                observed_at=EVALUATED_AT - timedelta(seconds=1),
                reason="mqtt-last-will",
            ),
            None,
        ),
        (
            "receiver_disconnected",
            StationHealthState.DEGRADED,
            fresh,
            _presence(),
            _pipeline(connection=ReceiverConnection.DISCONNECTED),
        ),
        (
            "receiver_pipeline_stale",
            StationHealthState.DEGRADED,
            fresh,
            _presence(),
            _pipeline(observed_at=EVALUATED_AT - timedelta(seconds=46)),
        ),
        (
            "receiver_queue_full",
            StationHealthState.DEGRADED,
            fresh,
            _presence(),
            _pipeline(queue_depth=128),
        ),
        (
            "receiver_source_silent",
            StationHealthState.DEGRADED,
            fresh,
            _presence(),
            _pipeline(last_message_age_seconds=301),
        ),
    ]


def _telemetry(**updates: object) -> StationTelemetry:
    values: dict[str, object] = {
        "message_id": UUID("00000000-0000-4000-8000-000000000001"),
        "node_id": "roof-node-1",
        "firmware_version": "0.1.0",
        "boot_id": UUID("00000000-0000-4000-8000-000000000002"),
        "sequence": 10,
        "observed_at": EVALUATED_AT - timedelta(seconds=5),
        "uptime_seconds": 600,
        "reconnect_count": 0,
        "rssi_dbm": -55,
        "free_heap_bytes": 120_000,
        "offline_queue_depth": 0,
        "watchdog_reset_count": 0,
    }
    values.update(updates)
    return StationTelemetry.model_validate(values)


def _presence(**updates: object) -> StationPresence:
    values: dict[str, object] = {
        "message_id": UUID("00000000-0000-4000-8000-000000000003"),
        "node_id": "roof-node-1",
        "status": PresenceStatus.ONLINE,
        "observed_at": EVALUATED_AT - timedelta(seconds=5),
        "reason": "connected",
    }
    values.update(updates)
    return StationPresence.model_validate(values)


def _pipeline(**updates: object) -> ReceiverPipelineTelemetry:
    values: dict[str, object] = {
        "message_id": UUID("00000000-0000-4000-8000-000000000004"),
        "node_id": "roof-node-1",
        "observed_at": EVALUATED_AT - timedelta(seconds=5),
        "connection": ReceiverConnection.CONNECTED,
        "policy_version": "feeder-v1",
        "last_message_age_seconds": 5,
        "queue_depth": 0,
        "queue_capacity": 128,
        "dropped_messages_total": 0,
        "reconnects_total": 0,
    }
    values.update(updates)
    return ReceiverPipelineTelemetry.model_validate(values)


def _implementation_hash() -> str:
    digest = hashlib.sha256()
    for path in IMPLEMENTATION_PATHS:
        digest.update(path.read_bytes())
    return digest.hexdigest()
