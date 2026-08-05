"""Deterministic offline evaluation for cross-source corroboration behavior."""

from __future__ import annotations

import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from statistics import median
from uuid import NAMESPACE_URL, uuid5

from ..schemas.observation import (
    ObservationProvenance,
    ObservationSourceType,
    TrackObservation,
)
from ..services.corroboration import CorroborationState, compare_observations


SUITE_VERSION = "1.0-offline-synthetic"
DEFAULT_START = datetime(2026, 8, 4, tzinfo=timezone.utc)


class Scenario(str, Enum):
    AGREEMENT = "AGREEMENT"
    LOCAL_ONLY = "LOCAL_ONLY"
    EXTERNAL_ONLY = "EXTERNAL_ONLY"
    POSITION_CONFLICT = "POSITION_CONFLICT"
    STALE_EXTERNAL = "STALE_EXTERNAL"
    PROVIDER_OUTAGE = "PROVIDER_OUTAGE"


EXPECTED_STATE = {
    Scenario.AGREEMENT: CorroborationState.CORROBORATED,
    Scenario.LOCAL_ONLY: CorroborationState.LOCAL_ONLY,
    Scenario.EXTERNAL_ONLY: CorroborationState.EXTERNAL_ONLY,
    Scenario.POSITION_CONFLICT: CorroborationState.CONFLICTING,
    Scenario.STALE_EXTERNAL: CorroborationState.STALE,
    Scenario.PROVIDER_OUTAGE: CorroborationState.UNAVAILABLE,
}


def run_corroboration_evaluation(
    *,
    hours: int = 4,
    interval_seconds: int = 20,
    implementation_revision: str = "working-tree",
) -> dict[str, object]:
    if hours <= 0 or interval_seconds <= 0:
        raise ValueError("hours and interval_seconds must be positive")
    comparison_count = hours * 3_600 // interval_seconds
    if comparison_count < len(Scenario):
        raise ValueError("evaluation must include every scenario")

    counts: Counter[str] = Counter()
    latencies: list[float] = []
    mismatches: list[dict[str, str]] = []
    conflict_samples: list[dict[str, object]] = []
    scenarios = tuple(Scenario)
    for index in range(comparison_count):
        scenario = scenarios[index % len(scenarios)]
        evaluated_at = DEFAULT_START + timedelta(seconds=index * interval_seconds)
        local, external, available, latency = _case(scenario, index, evaluated_at)
        result = compare_observations(
            local=local,
            external=external,
            evaluated_at=evaluated_at,
            source_available=available,
        )
        counts[result.state.value] += 1
        if latency is not None:
            latencies.append(latency)
        expected = EXPECTED_STATE[scenario]
        if result.state is not expected:
            mismatches.append(
                {
                    "scenario": scenario.value,
                    "expected": expected.value,
                    "actual": result.state.value,
                }
            )
        if (
            result.state is CorroborationState.CONFLICTING
            and len(conflict_samples) < 10
        ):
            conflict_samples.append(
                {
                    "icao_hex": result.icao_hex,
                    "evaluated_at": result.evaluated_at.isoformat(),
                    "position_distance_nm": result.position_distance_nm,
                    "altitude_difference_ft": result.altitude_difference_ft,
                    "synthetic_expectation": Scenario.POSITION_CONFLICT.value,
                    "human_review_status": "NOT_PERFORMED",
                }
            )

    unavailable = counts[CorroborationState.UNAVAILABLE.value]
    both_source = sum(
        counts[state.value]
        for state in (
            CorroborationState.CORROBORATED,
            CorroborationState.CONFLICTING,
            CorroborationState.STALE,
        )
    )
    return {
        "suite_version": SUITE_VERSION,
        "evidence_class": "OFFLINE_SYNTHETIC_ONLY",
        "implementation_revision": implementation_revision,
        "implementation_sha256": implementation_sha256(),
        "configuration": {
            "start": DEFAULT_START.isoformat(),
            "hours": hours,
            "interval_seconds": interval_seconds,
            "comparison_count": comparison_count,
            "scenario_cycle": [scenario.value for scenario in scenarios],
        },
        "results": {
            "classification_mismatches": mismatches,
            "state_counts": dict(sorted(counts.items())),
            "state_rates": {
                state.value: counts[state.value] / comparison_count
                for state in CorroborationState
            },
            "provider_availability_rate": (comparison_count - unavailable)
            / comparison_count,
            "both_source_coverage_rate": both_source / comparison_count,
            "simulated_external_latency_seconds": {
                "sample_count": len(latencies),
                "p50": median(latencies),
                "p95": _percentile(latencies, 0.95),
                "maximum": max(latencies),
            },
            "conflict_samples": conflict_samples,
        },
        "verification_boundaries": {
            "live_provider_requests": 0,
            "captured_rf_sessions": 0,
            "human_conflict_review": "NOT_PERFORMED",
            "field_coverage_claim_permitted": False,
            "field_latency_claim_permitted": False,
            "next_required_evidence": (
                "Run a permitted multi-hour live comparison and manually review "
                "a sample of real conflicts."
            ),
        },
    }


def passes_offline_gate(report: dict[str, object]) -> bool:
    results = report["results"]
    boundaries = report["verification_boundaries"]
    return bool(
        isinstance(results, dict)
        and not results["classification_mismatches"]
        and isinstance(boundaries, dict)
        and boundaries["live_provider_requests"] == 0
        and boundaries["field_coverage_claim_permitted"] is False
        and boundaries["field_latency_claim_permitted"] is False
    )


def implementation_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _case(
    scenario: Scenario,
    index: int,
    evaluated_at: datetime,
) -> tuple[TrackObservation | None, TrackObservation | None, bool, float | None]:
    icao_hex = f"{index % 0xFFFFFF:06X}"
    latency = 0.5 + (index % 5) * 0.5
    local = _observation(
        source_type=ObservationSourceType.SIMULATION,
        source_id="synthetic-local",
        icao_hex=icao_hex,
        observed_at=evaluated_at,
        received_at=evaluated_at,
        latitude=40.0,
        longitude=-75.0,
        index=index,
    )
    external = _observation(
        source_type=ObservationSourceType.EXTERNAL_FEED,
        source_id="synthetic-external",
        icao_hex=icao_hex,
        observed_at=evaluated_at,
        received_at=evaluated_at + timedelta(seconds=latency),
        latitude=40.005,
        longitude=-75.005,
        index=index,
    )
    if scenario is Scenario.LOCAL_ONLY:
        return local, None, True, None
    if scenario is Scenario.EXTERNAL_ONLY:
        return None, external, True, latency
    if scenario is Scenario.POSITION_CONFLICT:
        external = external.model_copy(update={"latitude": 41.0})
    elif scenario is Scenario.STALE_EXTERNAL:
        external = external.model_copy(
            update={"observed_at": evaluated_at - timedelta(seconds=31)}
        )
    elif scenario is Scenario.PROVIDER_OUTAGE:
        return local, None, False, None
    return local, external, True, latency


def _observation(
    *,
    source_type: ObservationSourceType,
    source_id: str,
    icao_hex: str,
    observed_at: datetime,
    received_at: datetime,
    latitude: float,
    longitude: float,
    index: int,
) -> TrackObservation:
    return TrackObservation(
        observation_id=uuid5(NAMESPACE_URL, f"{source_id}:{index}"),
        provenance=ObservationProvenance(
            source_type=source_type,
            source_id=source_id,
            provider=(
                "synthetic-fixture"
                if source_type is ObservationSourceType.EXTERNAL_FEED
                else None
            ),
        ),
        icao_hex=icao_hex,
        observed_at=observed_at,
        received_at=received_at,
        latitude=latitude,
        longitude=longitude,
        altitude_ft=10_000,
    )


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * percentile)]
