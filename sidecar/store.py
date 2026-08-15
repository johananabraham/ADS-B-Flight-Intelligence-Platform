"""Bounded append-only JSONL event storage with recovery."""

from __future__ import annotations

import json
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, TextIO


class RotatingEventStore:
    def __init__(
        self,
        directory: Path,
        *,
        retention_hours: int,
        max_bytes: int,
        segment_bytes: int | None = None,
    ) -> None:
        self.directory = directory
        self.retention = timedelta(hours=retention_hours)
        self.max_bytes = max_bytes
        self.segment_bytes = segment_bytes or min(8 * 1024 * 1024, max(64 * 1024, max_bytes // 8))
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._sequence = self._next_sequence()
        self._handle: TextIO | None = None
        self._path: Path | None = None
        self.recovered_events: deque[dict[str, Any]] = deque(
            self._recover(), maxlen=10_000
        )
        self._event_id_order: deque[str] = deque(
            (
                str(record["event_id"])
                for record in self.recovered_events
                if record.get("event_id")
            ),
            maxlen=10_000,
        )
        self._event_ids = set(self._event_id_order)
        self._open_segment()
        self.enforce_bounds()

    def _segments(self) -> list[Path]:
        return sorted(self.directory.glob("events-*.jsonl"))

    def _next_sequence(self) -> int:
        values: list[int] = []
        for path in self._segments():
            try:
                values.append(int(path.stem.rsplit("-", 1)[1]))
            except (IndexError, ValueError):
                continue
        return max(values, default=0) + 1

    def _open_segment(self) -> None:
        self._path = self.directory / f"events-{self._sequence:08d}.jsonl"
        self._sequence += 1
        self._handle = self._path.open("a", encoding="utf-8")

    def append(self, record: dict[str, Any]) -> None:
        encoded = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(encoded.encode()) + 1 > self.segment_bytes:
            raise ValueError("event exceeds JSONL segment size")
        if self._path and self._path.stat().st_size + len(encoded.encode()) + 1 > self.segment_bytes:
            self._rotate()
        assert self._handle is not None
        self._handle.write(encoded + "\n")
        self._handle.flush()
        os.fsync(self._handle.fileno())
        self.enforce_bounds()

    def _rotate(self) -> None:
        if self._handle:
            self._handle.close()
        self._open_segment()

    def _recover(self) -> list[dict[str, Any]]:
        recovered: list[dict[str, Any]] = []
        for path in self._segments():
            records, valid = self._read_segment(path)
            if valid:
                recovered.extend(records)
            else:
                path.replace(path.with_suffix(path.suffix + ".invalid"))
        return recovered

    @staticmethod
    def _read_segment(path: Path) -> tuple[list[dict[str, Any]], bool]:
        raw = path.read_bytes()
        lines = raw.splitlines(keepends=True)
        records: list[dict[str, Any]] = []
        for index, line in enumerate(lines):
            if not line.endswith((b"\n", b"\r")) and index == len(lines) - 1:
                break
            try:
                value = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                return [], False
            if not isinstance(value, dict) or value.get("schema_version") != "1.0":
                return [], False
            records.append(value)
        return records, True

    def query(
        self,
        *,
        since: datetime | None = None,
        state: str | None = None,
        kind: str | None = None,
        track_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for record in reversed(self.recovered_events):
            if self._matches(
                record, since=since, state=state, kind=kind, track_id=track_id
            ):
                results.append(record)
                if len(results) >= limit:
                    break
        return results

    @staticmethod
    def _matches(
        record: dict[str, Any],
        *,
        since: datetime | None,
        state: str | None,
        kind: str | None,
        track_id: str | None,
    ) -> bool:
        if track_id and record.get("track_id") != track_id:
            return False
        if state and record.get("state") != state:
            return False
        if kind and (record.get("evidence") or {}).get("kind") != kind:
            return False
        if since:
            try:
                observed = datetime.fromisoformat(str(record["observed_at"]).replace("Z", "+00:00"))
            except (KeyError, ValueError):
                return False
            if observed < since:
                return False
        return True

    def remember(self, record: dict[str, Any]) -> bool:
        event_id = str(record.get("event_id") or "")
        if event_id and event_id in self._event_ids:
            return False
        self.append(record)
        self.recovered_events.append(record)
        if event_id:
            if self._event_id_order.maxlen and len(self._event_id_order) == self._event_id_order.maxlen:
                self._event_ids.discard(self._event_id_order[0])
            self._event_id_order.append(event_id)
            self._event_ids.add(event_id)
        return True

    def enforce_bounds(self) -> None:
        segments = self._segments()
        cutoff = datetime.now(timezone.utc) - self.retention
        for path in segments:
            if path == self._path:
                continue
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if modified < cutoff:
                path.unlink(missing_ok=True)
        segments = self._segments()
        total = sum(path.stat().st_size for path in segments)
        for path in segments:
            if total <= self.max_bytes:
                break
            if path == self._path:
                continue
            size = path.stat().st_size
            path.unlink(missing_ok=True)
            total -= size

    def close(self) -> None:
        if self._handle:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> "RotatingEventStore":
        return self

    def __exit__(self, *_: Iterable[object]) -> None:
        self.close()
