#!/usr/bin/env python3
"""Reproducible 100-message/second feeder-sidecar soak gate."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from integrity_core import IntegrityEngine, load_policy
from sidecar.config import SidecarConfig
from sidecar.service import SidecarRuntime
from sidecar.store import RotatingEventStore


ROOT = Path(__file__).resolve().parents[1]


def sbs_line(index: int, rate: int, start: datetime) -> str:
    track_number = index % 100
    step = index // 100
    observed = start + timedelta(seconds=index / rate)
    latitude = track_number * 0.01 + step * (300 / 3600 / 60)
    aircraft_id = f"A{track_number:05X}"
    stamp_date = observed.strftime("%Y/%m/%d")
    stamp_time = observed.strftime("%H:%M:%S.%f")[:-3]
    return (
        f"MSG,3,1,1,{aircraft_id},1,{stamp_date},{stamp_time},"
        f"{stamp_date},{stamp_time},,10000,300,0,{latitude:.7f},0.0000000,0,1200,0,0,0,0"
    )


async def run(duration: int, rate: int, accelerated: bool) -> dict[str, float | int | bool]:
    start = datetime.now(timezone.utc).replace(microsecond=0)
    latencies: list[float] = []
    with tempfile.TemporaryDirectory(prefix="feeder-soak-") as directory:
        config = SidecarConfig(
            input_host="127.0.0.1",
            input_port=30003,
            receiver_id="soak-fixture",
            bind_host="127.0.0.1",
            port=8090,
            policy_path=ROOT / "backend/integrity_core/policies/feeder-v1.json",
            event_directory=Path(directory),
            retention_hours=1,
            store_max_mb=8,
            queue_maxsize=max(1024, rate * 10),
        )
        store = RotatingEventStore(config.event_directory, retention_hours=1, max_bytes=8 * 1024 * 1024)
        runtime = SidecarRuntime(config, IntegrityEngine(load_policy(config.policy_path)), store)
        count = duration * rate
        wall_start = time.perf_counter()
        for index in range(count):
            target = wall_start + index / rate
            if not accelerated and (remaining := target - time.perf_counter()) > 0:
                await asyncio.sleep(remaining)
            received_at = start + timedelta(seconds=index / rate)
            item_start = time.perf_counter()
            accepted = await runtime.process_line(
                sbs_line(index, rate, start), received_at=received_at
            )
            latencies.append(time.perf_counter() - item_start)
            if not accepted:
                raise RuntimeError(f"generated SBS line {index} was rejected")
        elapsed = time.perf_counter() - wall_start
        store.close()
        ordered = sorted(latencies)
        p95 = ordered[max(0, int(len(ordered) * 0.95) - 1)]
        return {
            "schema_version": "1.0",
            "duration_seconds": duration,
            "target_rate_messages_per_second": rate,
            "accelerated": accelerated,
            "messages": count,
            "wall_seconds": round(elapsed, 6),
            "achieved_rate_messages_per_second": round(count / elapsed, 3),
            "p50_processing_ms": round(statistics.median(latencies) * 1000, 3),
            "p95_processing_ms": round(p95 * 1000, 3),
            "dropped_messages_total": runtime.metrics.dropped,
            "process_memory_mb": round(runtime.metrics.memory_bytes() / 1024 / 1024, 3),
            "passed": runtime.metrics.dropped == 0
            and p95 < 0.1
            and runtime.metrics.memory_bytes() <= 256 * 1024 * 1024,
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=1800)
    parser.add_argument("--rate", type=int, default=100)
    parser.add_argument("--accelerated", action="store_true")
    args = parser.parse_args()
    if args.duration < 1 or not 1 <= args.rate <= 10_000:
        parser.error("duration and rate must be positive and bounded")
    report = asyncio.run(run(args.duration, args.rate, args.accelerated))
    print(json.dumps(report, sort_keys=True, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
