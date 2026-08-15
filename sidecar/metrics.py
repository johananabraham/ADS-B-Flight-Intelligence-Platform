"""Small dependency-free Prometheus exposition registry."""

from __future__ import annotations

import os
import resource
from collections import Counter


class Metrics:
    LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)

    def __init__(self) -> None:
        self.connection_state = 0
        self.reconnects = 0
        self.parsed = 0
        self.failures: Counter[str] = Counter()
        self.evaluated = 0
        self.queue_depth = 0
        self.dropped = 0
        self.latency_count = 0
        self.latency_sum = 0.0
        self.latency_buckets: Counter[float] = Counter()

    def observe_latency(self, seconds: float) -> None:
        self.latency_count += 1
        self.latency_sum += seconds
        for bucket in self.LATENCY_BUCKETS:
            if seconds <= bucket:
                self.latency_buckets[bucket] += 1

    @staticmethod
    def memory_bytes() -> int:
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return int(rss if os.uname().sysname == "Darwin" else rss * 1024)

    def render(self, snapshots: tuple) -> str:
        lines = [
            "# TYPE adsb_sidecar_connection_state gauge",
            f"adsb_sidecar_connection_state {self.connection_state}",
            "# TYPE adsb_sidecar_reconnects_total counter",
            f"adsb_sidecar_reconnects_total {self.reconnects}",
            "# TYPE adsb_sidecar_parsed_messages_total counter",
            f"adsb_sidecar_parsed_messages_total {self.parsed}",
        ]
        for reason in sorted(self.failures):
            lines.append(
                f'adsb_sidecar_parse_failures_total{{reason="{reason}"}} {self.failures[reason]}'
            )
        lines.extend(
            [
                "# TYPE adsb_sidecar_observations_evaluated_total counter",
                f"adsb_sidecar_observations_evaluated_total {self.evaluated}",
                "# TYPE adsb_sidecar_queue_depth gauge",
                f"adsb_sidecar_queue_depth {self.queue_depth}",
                "# TYPE adsb_sidecar_dropped_messages_total counter",
                f"adsb_sidecar_dropped_messages_total {self.dropped}",
                "# TYPE adsb_sidecar_process_memory_bytes gauge",
                f"adsb_sidecar_process_memory_bytes {self.memory_bytes()}",
            ]
        )
        state_counts = Counter(item.state.value for item in snapshots)
        evidence_counts = Counter(
            evidence.kind.value for item in snapshots for evidence in item.active_evidence
        )
        for state in ("NOMINAL", "QUESTIONABLE", "INSUFFICIENT_DATA"):
            lines.append(f'adsb_sidecar_tracks{{state="{state}"}} {state_counts[state]}')
        for kind in (
            "PAIR_KINEMATIC",
            "WINDOW_KINEMATIC",
            "TIMING_DUPLICATE",
            "TIMING_NON_INCREASING",
            "TIMING_OUT_OF_ORDER",
            "TIMING_EXCESSIVE_LATENCY",
            "TIMING_GAP",
        ):
            lines.append(f'adsb_sidecar_open_evidence{{kind="{kind}"}} {evidence_counts[kind]}')
        cumulative = 0
        for bucket in self.LATENCY_BUCKETS:
            cumulative = self.latency_buckets[bucket]
            lines.append(
                f'adsb_sidecar_processing_latency_seconds_bucket{{le="{bucket}"}} {cumulative}'
            )
        lines.extend(
            [
                f'adsb_sidecar_processing_latency_seconds_bucket{{le="+Inf"}} {self.latency_count}',
                f"adsb_sidecar_processing_latency_seconds_count {self.latency_count}",
                f"adsb_sidecar_processing_latency_seconds_sum {self.latency_sum:.9f}",
            ]
        )
        return "\n".join(lines) + "\n"
