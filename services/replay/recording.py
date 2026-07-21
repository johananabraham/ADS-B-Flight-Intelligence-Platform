"""Validation and deterministic scheduling for recorded SBS playback."""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_left
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
SUPPORTED_SPEEDS = frozenset({0.5, 1.0, 2.0, 10.0})


class RecordingValidationError(ValueError):
    """Raised when a recording cannot be trusted for deterministic playback."""


def _parse_timestamp(value: str, field_name: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RecordingValidationError(f"{field_name} must be an ISO 8601 timestamp") from exc
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise RecordingValidationError(f"{field_name} must include a timezone")
    return timestamp.astimezone(timezone.utc)


def _events_hash(events: list[dict[str, Any]]) -> str:
    encoded = json.dumps(events, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class RecordingSource:
    kind: str
    name: str
    license_id: str
    attribution: str


@dataclass(frozen=True)
class RecordingEvent:
    offset_ms: int
    observed_at: datetime
    sbs_message: str


@dataclass(frozen=True)
class Recording:
    recording_id: str
    title: str
    description: str
    created_at: datetime
    start_time: datetime
    source: RecordingSource
    receiver_id: str | None
    events_sha256: str
    events: tuple[RecordingEvent, ...]

    @classmethod
    def load(cls, path: str | Path) -> "Recording":
        try:
            document = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RecordingValidationError(f"cannot read recording: {exc}") from exc
        return cls.from_dict(document)

    @classmethod
    def from_dict(cls, document: dict[str, Any]) -> "Recording":
        if not isinstance(document, dict):
            raise RecordingValidationError("recording document must be an object")
        if document.get("schema_version") != SCHEMA_VERSION:
            raise RecordingValidationError(f"schema_version must be {SCHEMA_VERSION}")

        source_data = document.get("source")
        events_data = document.get("events")
        if not isinstance(source_data, dict):
            raise RecordingValidationError("source must be an object")
        if not isinstance(events_data, list) or not events_data:
            raise RecordingValidationError("events must be a non-empty list")

        expected_hash = document.get("events_sha256")
        actual_hash = _events_hash(events_data)
        if expected_hash != actual_hash:
            raise RecordingValidationError("events_sha256 does not match recording events")

        start_time = _parse_timestamp(document.get("start_time"), "start_time")
        events: list[RecordingEvent] = []
        previous_offset = -1
        for index, event_data in enumerate(events_data):
            event = cls._parse_event(event_data, index, start_time)
            if event.offset_ms < previous_offset:
                raise RecordingValidationError("events must be ordered by offset_ms")
            previous_offset = event.offset_ms
            events.append(event)

        required_text = {
            "recording_id": document.get("recording_id"),
            "title": document.get("title"),
            "description": document.get("description"),
            "source.kind": source_data.get("kind"),
            "source.name": source_data.get("name"),
            "source.license_id": source_data.get("license_id"),
            "source.attribution": source_data.get("attribution"),
        }
        missing = [name for name, value in required_text.items() if not isinstance(value, str) or not value.strip()]
        if missing:
            raise RecordingValidationError(f"missing required text fields: {', '.join(missing)}")

        receiver_id = document.get("receiver_id")
        if receiver_id is not None and (not isinstance(receiver_id, str) or not receiver_id.strip()):
            raise RecordingValidationError("receiver_id must be null or non-empty text")

        return cls(
            recording_id=document["recording_id"],
            title=document["title"],
            description=document["description"],
            created_at=_parse_timestamp(document.get("created_at"), "created_at"),
            start_time=start_time,
            source=RecordingSource(
                kind=source_data["kind"],
                name=source_data["name"],
                license_id=source_data["license_id"],
                attribution=source_data["attribution"],
            ),
            receiver_id=receiver_id,
            events_sha256=actual_hash,
            events=tuple(events),
        )

    @staticmethod
    def _parse_event(
        event_data: Any,
        index: int,
        start_time: datetime,
    ) -> RecordingEvent:
        if not isinstance(event_data, dict):
            raise RecordingValidationError(f"event {index} must be an object")
        offset_ms = event_data.get("offset_ms")
        message = event_data.get("sbs_message")
        if not isinstance(offset_ms, int) or isinstance(offset_ms, bool) or offset_ms < 0:
            raise RecordingValidationError(f"event {index} offset_ms must be a non-negative integer")
        if not isinstance(message, str) or "\n" in message or "\r" in message:
            raise RecordingValidationError(f"event {index} must contain one SBS message")
        try:
            message.encode("ascii")
        except UnicodeEncodeError as exc:
            raise RecordingValidationError(f"event {index} SBS message must be ASCII") from exc

        observed_at = _parse_timestamp(event_data.get("observed_at"), f"event {index} observed_at")
        expected_offset = round((observed_at - start_time).total_seconds() * 1_000)
        if expected_offset != offset_ms:
            raise RecordingValidationError(f"event {index} timestamp does not match offset_ms")

        fields = message.split(",")
        if len(fields) < 8 or fields[0] != "MSG":
            raise RecordingValidationError(f"event {index} is not an SBS MSG record")
        try:
            sbs_observed_at = datetime.strptime(
                f"{fields[6]} {fields[7]}",
                "%Y/%m/%d %H:%M:%S.%f",
            ).replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise RecordingValidationError(f"event {index} has an invalid SBS timestamp") from exc
        if sbs_observed_at != observed_at:
            raise RecordingValidationError(f"event {index} SBS timestamp does not match observed_at")

        return RecordingEvent(offset_ms=offset_ms, observed_at=observed_at, sbs_message=message)


@dataclass(frozen=True)
class ScheduledEvent:
    delay_seconds: float
    event: RecordingEvent


class PlaybackCursor:
    """A per-client deterministic cursor over an immutable recording."""

    def __init__(self, recording: Recording, speed: float = 1.0) -> None:
        self.recording = recording
        self._offsets = [event.offset_ms for event in recording.events]
        self._position = 0
        self._playhead_ms = 0
        self.speed = 1.0
        self.set_speed(speed)

    def set_speed(self, speed: float) -> None:
        if speed not in SUPPORTED_SPEEDS:
            allowed = ", ".join(str(value) for value in sorted(SUPPORTED_SPEEDS))
            raise ValueError(f"speed must be one of: {allowed}")
        self.speed = speed

    def seek(self, offset_seconds: float) -> None:
        if offset_seconds < 0:
            raise ValueError("seek offset cannot be negative")
        self._playhead_ms = round(offset_seconds * 1_000)
        self._position = bisect_left(self._offsets, self._playhead_ms)

    def restart(self) -> None:
        self._position = 0
        self._playhead_ms = 0

    def next_event(self) -> ScheduledEvent | None:
        if self._position >= len(self.recording.events):
            return None
        event = self.recording.events[self._position]
        delay_seconds = max(0, event.offset_ms - self._playhead_ms) / 1_000 / self.speed
        self._position += 1
        self._playhead_ms = event.offset_ms
        return ScheduledEvent(delay_seconds=delay_seconds, event=event)
