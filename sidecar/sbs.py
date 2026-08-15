"""Strict SBS/BaseStation line adapter."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


MAX_SBS_LINE_BYTES = 4096


class ParseFailure(str, Enum):
    ENCODING = "encoding"
    TOO_LONG = "too_long"
    TOO_FEW_FIELDS = "too_few_fields"
    UNSUPPORTED_TYPE = "unsupported_type"
    INVALID_AIRCRAFT_ID = "invalid_aircraft_id"
    INVALID_TIMESTAMP = "invalid_timestamp"
    INVALID_VALUE = "invalid_value"


@dataclass(frozen=True)
class ParseResult:
    data: dict[str, object] | None
    failure: ParseFailure | None = None


def _timestamp(date_value: str, time_value: str) -> datetime | None:
    text = f"{date_value.strip()} {time_value.strip()}"
    for pattern in ("%Y/%m/%d %H:%M:%S.%f", "%Y/%m/%d %H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return None


def parse_sbs_line(raw: bytes | str) -> ParseResult:
    if isinstance(raw, bytes):
        if len(raw) > MAX_SBS_LINE_BYTES:
            return ParseResult(None, ParseFailure.TOO_LONG)
        try:
            line = raw.decode("utf-8", errors="strict")
        except UnicodeDecodeError:
            return ParseResult(None, ParseFailure.ENCODING)
    else:
        line = raw
        if len(line.encode("utf-8")) > MAX_SBS_LINE_BYTES:
            return ParseResult(None, ParseFailure.TOO_LONG)
    normalized = line.strip()
    parts = normalized.split(",")
    if len(parts) < 11:
        return ParseResult(None, ParseFailure.TOO_FEW_FIELDS)
    if parts[0] != "MSG":
        return ParseResult(None, ParseFailure.UNSUPPORTED_TYPE)
    aircraft_id = parts[4].strip().upper()
    if len(aircraft_id) != 6 or any(char not in "0123456789ABCDEF" for char in aircraft_id):
        return ParseResult(None, ParseFailure.INVALID_AIRCRAFT_ID)
    observed_at = _timestamp(parts[6], parts[7])
    if observed_at is None:
        return ParseResult(None, ParseFailure.INVALID_TIMESTAMP)
    data: dict[str, object] = {
        "hex": aircraft_id,
        "_observed_at": observed_at,
        "_raw_message_id": hashlib.sha256(normalized.encode()).hexdigest(),
    }
    fields: tuple[tuple[int, str, type], ...] = (
        (10, "flight", str),
        (11, "altitude", int),
        (12, "gs", float),
        (13, "track", float),
        (14, "lat", float),
        (15, "lon", float),
        (16, "vert_rate", int),
        (17, "squawk", str),
    )
    try:
        for index, name, converter in fields:
            if index < len(parts) and parts[index].strip():
                data[name] = converter(parts[index].strip())
    except ValueError:
        return ParseResult(None, ParseFailure.INVALID_VALUE)
    return ParseResult(data)


def merge_state(existing: dict[str, object] | None, update: dict[str, object]) -> dict[str, object]:
    merged = dict(existing or {"hex": update["hex"]})
    for key, value in update.items():
        if value is not None and not key.startswith("_"):
            merged[key] = value
    merged["_observed_at"] = update["_observed_at"]
    merged["_raw_message_id"] = update["_raw_message_id"]
    return merged
