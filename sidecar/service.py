"""Bounded SBS ingestion and integrity evaluation runtime."""

from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.schemas.observation import ObservationSourceType
from app.services.observation_adapters import sbs_state_to_observation
from integrity_core import IntegrityEngine

from .config import SidecarConfig
from .metrics import Metrics
from .sbs import MAX_SBS_LINE_BYTES, merge_state, parse_sbs_line
from .store import RotatingEventStore


logger = logging.getLogger(__name__)


@dataclass
class ReceiverHealth:
    connection: str = "DISCONNECTED"
    detail: str = "Waiting for the SBS source."
    connected_at: datetime | None = None
    last_message_at: datetime | None = None


class SidecarRuntime:
    def __init__(
        self,
        config: SidecarConfig,
        engine: IntegrityEngine,
        store: RotatingEventStore,
    ) -> None:
        self.config = config
        self.engine = engine
        self.store = store
        self.metrics = Metrics()
        self.health = ReceiverHealth()
        self.queue: asyncio.Queue[tuple[bytes, datetime]] = asyncio.Queue(
            maxsize=config.queue_maxsize
        )
        self._states: dict[str, dict[str, object]] = {}
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._tasks: list[asyncio.Task] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._read_loop(), name="sbs-reader"),
            asyncio.create_task(self._process_loop(), name="integrity-processor"),
        ]

    async def stop(self) -> None:
        self._stopping.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self.store.close()

    async def _read_loop(self) -> None:
        delay = 1.0
        while not self._stopping.is_set():
            writer = None
            try:
                reader, writer = await asyncio.open_connection(
                    self.config.input_host,
                    self.config.input_port,
                    limit=MAX_SBS_LINE_BYTES + 1,
                )
                self.metrics.connection_state = 1
                self.health = ReceiverHealth(
                    connection="CONNECTED",
                    detail="SBS source connected and awaiting telemetry.",
                    connected_at=datetime.now(timezone.utc),
                )
                await self.publish({"type": "receiver_health", "health": self.health_dict()})
                delay = 1.0
                while not self._stopping.is_set():
                    try:
                        line = await reader.readline()
                    except ValueError:
                        self.metrics.failures["too_long"] += 1
                        self.health.connection = "DEGRADED"
                        self.health.detail = "An oversized SBS frame was rejected."
                        continue
                    if not line:
                        break
                    received_at = datetime.now(timezone.utc)
                    self.enqueue(line, received_at)
            except (ConnectionError, OSError) as exc:
                logger.warning("SBS source unavailable: %s", type(exc).__name__)
            finally:
                if writer is not None:
                    writer.close()
                    await writer.wait_closed()
                self.metrics.connection_state = 0
                self.health.connection = "DISCONNECTED"
                self.health.detail = "SBS source disconnected; reconnect is automatic."
                await self.publish({"type": "receiver_health", "health": self.health_dict()})
            if self._stopping.is_set():
                return
            self.metrics.reconnects += 1
            await asyncio.sleep(delay + random.uniform(0, min(0.5, delay / 4)))
            delay = min(delay * 2, 30.0)

    async def _process_loop(self) -> None:
        while not self._stopping.is_set():
            raw, received_at = await self.queue.get()
            started = time.perf_counter()
            try:
                await self.process_line(raw, received_at=received_at)
            finally:
                self.queue.task_done()
                self.metrics.queue_depth = self.queue.qsize()
                self.metrics.observe_latency(time.perf_counter() - started)

    async def process_line(
        self,
        raw: bytes | str,
        *,
        received_at: datetime | None = None,
        source_type: ObservationSourceType = ObservationSourceType.LIVE_RF,
        recording_id: str | None = None,
    ) -> bool:
        parsed = parse_sbs_line(raw)
        if parsed.failure is not None:
            self.metrics.failures[parsed.failure.value] += 1
            return False
        assert parsed.data is not None
        self.metrics.parsed += 1
        aircraft_id = str(parsed.data["hex"])
        merged = merge_state(self._states.get(aircraft_id), parsed.data)
        self._states[aircraft_id] = merged
        if len(self._states) > self.engine.policy.runtime.maximum_tracks:
            oldest = min(
                self._states,
                key=lambda item: (self._states[item]["_observed_at"], item),
            )
            del self._states[oldest]
        received = received_at or datetime.now(timezone.utc)
        observed = parsed.data["_observed_at"]
        assert isinstance(observed, datetime)
        observation = sbs_state_to_observation(
            merged,
            source_type=source_type,
            source_id="local-sbs",
            receiver_id=self.config.receiver_id if source_type is ObservationSourceType.LIVE_RF else None,
            recording_id=recording_id if source_type is ObservationSourceType.RECORDED_REPLAY else None,
            observed_at=observed,
            received_at=received,
            raw_message_id=str(parsed.data["_raw_message_id"]),
        )
        snapshot, events = self.engine.ingest(observation)
        self.metrics.evaluated += 1
        self.health.last_message_at = received
        if self.metrics.connection_state:
            self.health.connection = "CONNECTED"
            self.health.detail = "SBS source connected and telemetry is being evaluated."
        for event in events:
            record = event.public_dict()
            self.store.remember(record)
            await self.publish({"type": event.event_type.value, "event": record})
        await self.publish({"type": "snapshot", "snapshot": snapshot.public_dict()})
        return True

    def enqueue(self, raw: bytes, received_at: datetime) -> bool:
        try:
            self.queue.put_nowait((raw, received_at))
        except asyncio.QueueFull:
            self.metrics.dropped += 1
            self.health.connection = "DEGRADED"
            self.health.detail = "The bounded processing queue is full; drops are reported."
            return False
        finally:
            self.metrics.queue_depth = self.queue.qsize()
        return True

    def health_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "connection": self.health.connection,
            "detail": self.health.detail,
            "source_mode": "LIVE",
            "policy_version": self.engine.policy.policy_version,
            "connected_at": self._time(self.health.connected_at),
            "last_message_at": self._time(self.health.last_message_at),
            "queue_depth": self.metrics.queue_depth,
            "queue_capacity": self.config.queue_maxsize,
            "dropped_messages_total": self.metrics.dropped,
            "reconnects_total": self.metrics.reconnects,
        }

    @staticmethod
    def _time(value: datetime | None) -> str | None:
        return value.isoformat().replace("+00:00", "Z") if value else None

    def subscribe(self) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=128)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers.discard(queue)

    async def publish(self, message: dict[str, Any]) -> None:
        stale: list[asyncio.Queue[dict[str, Any]]] = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(message)
            except asyncio.QueueFull:
                stale.append(queue)
        for queue in stale:
            self._subscribers.discard(queue)
