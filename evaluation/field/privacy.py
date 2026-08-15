"""Allow-list and leak checks for public benign feature exports."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable


ALLOWED_FIELDS = frozenset(
    {
        "export_schema_version",
        "public_session_id",
        "public_track_id",
        "elapsed_seconds",
        "delta_east_nm",
        "delta_north_nm",
        "relative_altitude_ft",
        "ground_speed_knots",
        "track_degrees",
        "vertical_rate_fpm",
        "position_missing",
        "altitude_missing",
        "receiver_health_class",
        "policy_state",
        "evidence_kinds",
        "measured",
        "thresholds",
        "reviewer_disposition",
        "split",
    }
)
FORBIDDEN_KEY_PARTS = (
    "icao",
    "callsign",
    "registration",
    "squawk",
    "latitude",
    "longitude",
    "receiver_id",
    "receiver_location",
    "timestamp",
    "observed_at",
    "date",
    "filename",
    "path",
    "salt",
    "ip_address",
    "origin",
    "destination",
)
DATE_PATTERN = re.compile(r"\b(?:19|20)\d{2}[-/]\d{2}[-/]\d{2}\b")
TIME_PATTERN = re.compile(r"\b\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b")
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
ABSOLUTE_PATH_PATTERN = re.compile(r"(?:^|[\s\"'])(?:/Users/|/home/|[A-Za-z]:\\)")


class PrivacyViolation(ValueError):
    """Raised when a public artifact violates its strict privacy contract."""


def verify_public_export(
    path: str | Path,
    *,
    known_private_values: Iterable[str] = (),
) -> int:
    source = Path(path)
    rows = []
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PrivacyViolation(f"line {line_number} is not valid JSON") from exc
        if not isinstance(row, dict):
            raise PrivacyViolation(f"line {line_number} must be an object")
        unknown = set(row) - ALLOWED_FIELDS
        if unknown:
            raise PrivacyViolation(f"line {line_number} has non-allow-listed fields: {sorted(unknown)}")
        for key in row:
            lowered = key.lower()
            if any(part in lowered for part in FORBIDDEN_KEY_PARTS):
                raise PrivacyViolation(f"line {line_number} has forbidden field {key}")
        rows.append(row)
    serialized = "\n".join(json.dumps(row, sort_keys=True) for row in rows)
    for pattern, label in (
        (DATE_PATTERN, "calendar date"),
        (TIME_PATTERN, "wall-clock time"),
        (IP_PATTERN, "network address"),
        (ABSOLUTE_PATH_PATTERN, "private filesystem path"),
    ):
        if pattern.search(serialized):
            raise PrivacyViolation(f"export contains a {label}")
    for value in known_private_values:
        if value and value.casefold() in serialized.casefold():
            raise PrivacyViolation("export contains a known private identifier")
    return len(rows)
