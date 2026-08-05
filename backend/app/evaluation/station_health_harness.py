"""Deterministic offline evidence for edge-station health classification."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from ..schemas.edge import PresenceStatus, StationPresence, StationTelemetry
from ..services.station_health import StationHealthState, evaluate_station_health


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
    for name, expected, telemetry, presence in scenarios:
        result = evaluate_station_health(
            telemetry=telemetry,
            presence=presence,
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
        "suite_version": "1.0-offline-synthetic",
        "evidence_class": "OFFLINE_SYNTHETIC_ONLY",
        "implementation_revision": implementation_revision,
        "implementation_sha256": _implementation_hash(),
        "configuration": {
            "evaluated_at": EVALUATED_AT.isoformat(),
            "scenario_count": len(scenarios),
            "policy_version": "1.0",
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


def _scenarios() -> (
    list[
        tuple[
            str,
            StationHealthState,
            StationTelemetry | None,
            StationPresence | None,
        ]
    ]
):
    fresh = _telemetry()
    return [
        ("no_data", StationHealthState.NO_DATA, None, None),
        ("fresh_nominal", StationHealthState.HEALTHY, fresh, _presence()),
        (
            "weak_wifi",
            StationHealthState.DEGRADED,
            _telemetry(rssi_dbm=-85),
            _presence(),
        ),
        (
            "offline_backpressure",
            StationHealthState.DEGRADED,
            _telemetry(offline_queue_depth=4),
            _presence(),
        ),
        (
            "watchdog_recovery",
            StationHealthState.DEGRADED,
            _telemetry(watchdog_reset_count=1),
            _presence(),
        ),
        (
            "heartbeat_timeout",
            StationHealthState.STALE,
            _telemetry(observed_at=EVALUATED_AT - timedelta(seconds=46)),
            _presence(observed_at=EVALUATED_AT - timedelta(seconds=46)),
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


def _implementation_hash() -> str:
    digest = hashlib.sha256()
    for path in IMPLEMENTATION_PATHS:
        digest.update(path.read_bytes())
    return digest.hexdigest()
