"""Interruptible playback state shared by the replay stream and control API."""

from __future__ import annotations

import asyncio
import time
from bisect import bisect_left
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Callable

from services.replay.recording import Recording, RecordingEvent, SUPPORTED_SPEEDS


class PlaybackState(str, Enum):
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class PlaybackSnapshot:
    recording_id: str
    title: str
    state: PlaybackState
    speed: float
    position_ms: int
    duration_ms: int
    event_index: int
    event_count: int
    loop: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class ReplayController:
    """Maintain one authoritative playback clock for the ingestion stream."""

    def __init__(
        self,
        recording: Recording,
        *,
        speed: float = 1.0,
        loop: bool = True,
        loop_delay_seconds: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if speed not in SUPPORTED_SPEEDS:
            raise ValueError("unsupported replay speed")
        if loop_delay_seconds < 0:
            raise ValueError("loop delay cannot be negative")
        self.recording = recording
        self.speed = speed
        self.loop = loop
        self.loop_delay_seconds = loop_delay_seconds
        self.state = PlaybackState.PLAYING
        self._clock = clock
        self._anchor_time = clock()
        self._position_ms = 0.0
        self._event_index = 0
        self._offsets = [event.offset_ms for event in recording.events]
        self._duration_ms = self._offsets[-1]
        self._lock = asyncio.Lock()
        self._changed = asyncio.Event()

    def _current_position(self) -> float:
        if self.state is not PlaybackState.PLAYING:
            return self._position_ms
        elapsed_ms = (self._clock() - self._anchor_time) * 1_000 * self.speed
        return min(self._duration_ms, self._position_ms + elapsed_ms)

    def _freeze_position(self) -> None:
        self._position_ms = self._current_position()
        self._anchor_time = self._clock()

    def _snapshot(self) -> PlaybackSnapshot:
        return PlaybackSnapshot(
            recording_id=self.recording.recording_id,
            title=self.recording.title,
            state=self.state,
            speed=self.speed,
            position_ms=round(self._current_position()),
            duration_ms=self._duration_ms,
            event_index=self._event_index,
            event_count=len(self.recording.events),
            loop=self.loop,
        )

    async def status(self) -> PlaybackSnapshot:
        async with self._lock:
            return self._snapshot()

    async def pause(self) -> PlaybackSnapshot:
        async with self._lock:
            if self.state is PlaybackState.PLAYING:
                self._freeze_position()
                self.state = PlaybackState.PAUSED
            self._changed.set()
            return self._snapshot()

    async def resume(self) -> PlaybackSnapshot:
        async with self._lock:
            if self.state is PlaybackState.PAUSED:
                self._anchor_time = self._clock()
                self.state = PlaybackState.PLAYING
            self._changed.set()
            return self._snapshot()

    async def restart(self) -> PlaybackSnapshot:
        async with self._lock:
            self._position_ms = 0
            self._event_index = 0
            self._anchor_time = self._clock()
            self.state = PlaybackState.PLAYING
            self._changed.set()
            return self._snapshot()

    async def seek(self, offset_seconds: float) -> PlaybackSnapshot:
        if offset_seconds < 0:
            raise ValueError("seek offset cannot be negative")
        async with self._lock:
            self._position_ms = min(offset_seconds * 1_000, self._duration_ms)
            self._event_index = bisect_left(self._offsets, self._position_ms)
            self._anchor_time = self._clock()
            if self.state is PlaybackState.COMPLETED:
                self.state = PlaybackState.PAUSED
            self._changed.set()
            return self._snapshot()

    async def set_speed(self, speed: float) -> PlaybackSnapshot:
        if speed not in SUPPORTED_SPEEDS:
            raise ValueError("unsupported replay speed")
        async with self._lock:
            self._freeze_position()
            self.speed = speed
            self._changed.set()
            return self._snapshot()

    async def next_event(self) -> RecordingEvent:
        """Wait until the next event is due, waking immediately for control changes."""
        while True:
            loop_wait = False
            async with self._lock:
                self._changed.clear()
                if self.state is PlaybackState.PLAYING:
                    position_ms = self._current_position()
                    if self._event_index < len(self.recording.events):
                        event = self.recording.events[self._event_index]
                        if event.offset_ms <= position_ms:
                            self._event_index += 1
                            return event
                        timeout = (event.offset_ms - position_ms) / 1_000 / self.speed
                    else:
                        self._position_ms = self._duration_ms
                        self.state = PlaybackState.COMPLETED
                        timeout = self.loop_delay_seconds if self.loop else None
                        loop_wait = self.loop
                else:
                    timeout = None

            try:
                if timeout is None:
                    await self._changed.wait()
                else:
                    await asyncio.wait_for(self._changed.wait(), timeout=timeout)
            except TimeoutError:
                if loop_wait:
                    await self.restart()
