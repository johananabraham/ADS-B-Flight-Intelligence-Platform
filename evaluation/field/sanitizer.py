"""Convert private SBS captures into nonreversible relative feature rows."""

from __future__ import annotations

import json
import hashlib
import math
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.observation import ObservationSourceType
from app.services.observation_adapters import sbs_state_to_observation
from integrity_core import IntegrityEngine, load_policy
from sidecar.sbs import merge_state, parse_sbs_line

from .privacy import verify_public_export


SPLITS = {1: "development", 2: "development", 3: "development", 4: "development", 5: "validation", 6: "validation", 7: "holdout"}
EXCLUSION_REASONS = {"SOURCE_OUTAGE", "CAPTURE_RESTART", "CONFIGURATION_CHANGE", "OTHER_DOCUMENTED"}


def _label(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(12)}"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sanitize_capture(
    manifest_path: str | Path,
    policy_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    manifest_file = Path(manifest_path)
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "1.0":
        raise ValueError("capture manifest schema_version 1.0 is required")
    policy = load_policy(policy_path)
    output = Path(output_path)
    if output.suffix != ".jsonl":
        raise ValueError("public export must use a .jsonl filename")
    session_labels: dict[int, str] = {}
    track_labels: dict[tuple[int, str], str] = {}
    origins: dict[tuple[int, str], tuple[float, float, int | None]] = {}
    states: dict[tuple[int, str], dict[str, object]] = {}
    known_private: set[str] = set(manifest.get("known_private_values", []))
    rows: list[dict[str, Any]] = []
    public_sessions: list[dict[str, Any]] = []

    for capture in sorted(manifest.get("captures", []), key=lambda item: item["day"]):
        day = int(capture["day"])
        if day not in SPLITS or not capture.get("usable", False):
            continue
        capture_path = Path(capture["path"])
        if not capture_path.is_absolute():
            capture_path = manifest_file.parent / capture_path
        expected_sha = capture.get("sha256")
        if not expected_sha or _sha256(capture_path) != expected_sha:
            raise ValueError(f"capture day {day} checksum does not match its manifest")
        session_labels[day] = _label("session")
        engine = IntegrityEngine(policy)
        session_start: datetime | None = None
        session_end: datetime | None = None
        for raw_line in capture_path.read_bytes().splitlines():
            parsed = parse_sbs_line(raw_line)
            if parsed.data is None:
                continue
            aircraft_id = str(parsed.data["hex"])
            known_private.add(aircraft_id)
            callsign = parsed.data.get("flight")
            if callsign:
                known_private.add(str(callsign))
            key = (day, aircraft_id)
            merged = merge_state(states.get(key), parsed.data)
            states[key] = merged
            observed_at = parsed.data["_observed_at"]
            assert isinstance(observed_at, datetime)
            session_start = session_start or observed_at
            session_end = observed_at
            observation = sbs_state_to_observation(
                merged,
                source_type=ObservationSourceType.RECORDED_REPLAY,
                source_id="private-field-capture",
                recording_id=f"private-day-{day}",
                observed_at=observed_at,
                received_at=observed_at,
                raw_message_id=str(parsed.data["_raw_message_id"]),
            )
            snapshot, _ = engine.ingest(observation)
            latitude = merged.get("lat")
            longitude = merged.get("lon")
            altitude = merged.get("altitude")
            if key not in origins and latitude is not None and longitude is not None:
                origins[key] = (float(latitude), float(longitude), int(altitude) if altitude is not None else None)
            origin = origins.get(key)
            delta_north = delta_east = None
            relative_altitude = None
            if origin and latitude is not None and longitude is not None:
                delta_north = round((float(latitude) - origin[0]) * 60, 6)
                delta_east = round(
                    (float(longitude) - origin[1]) * 60 * math.cos(math.radians(origin[0])),
                    6,
                )
            if origin and origin[2] is not None and altitude is not None:
                relative_altitude = int(altitude) - origin[2]
            track_labels.setdefault(key, _label("track"))
            measured = {
                metric: value
                for evidence in snapshot.active_evidence
                for metric, value in evidence.measured.items()
            }
            thresholds = {
                metric: value
                for evidence in snapshot.active_evidence
                for metric, value in evidence.thresholds.items()
            }
            rows.append(
                {
                    "export_schema_version": "1.0",
                    "public_session_id": session_labels[day],
                    "public_track_id": track_labels[key],
                    "elapsed_seconds": round((observed_at - session_start).total_seconds(), 3),
                    "delta_east_nm": delta_east,
                    "delta_north_nm": delta_north,
                    "relative_altitude_ft": relative_altitude,
                    "ground_speed_knots": merged.get("gs"),
                    "track_degrees": merged.get("track"),
                    "vertical_rate_fpm": merged.get("vert_rate"),
                    "position_missing": latitude is None or longitude is None,
                    "altitude_missing": altitude is None,
                    "receiver_health_class": "NOMINAL",
                    "policy_state": snapshot.state.value,
                    "evidence_kinds": sorted({item.kind.value for item in snapshot.active_evidence}),
                    "measured": measured,
                    "thresholds": thresholds,
                    "reviewer_disposition": "UNREVIEWED",
                    "split": SPLITS[day],
                }
            )
        exclusions = []
        if session_start:
            for interval in capture.get("excluded_intervals", capture.get("outages", [])):
                reason = interval.get("reason", "SOURCE_OUTAGE")
                if reason not in EXCLUSION_REASONS:
                    raise ValueError(f"capture day {day} has unsupported exclusion reason")
                start = datetime.fromisoformat(interval["started_at"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(interval["ended_at"].replace("Z", "+00:00"))
                exclusions.append(
                    {
                        "start_seconds": round((start - session_start).total_seconds(), 3),
                        "end_seconds": round((end - session_start).total_seconds(), 3),
                        "reason": reason,
                    }
                )
        public_sessions.append(
            {
                "public_session_id": session_labels[day],
                "split": SPLITS[day],
                "usable_duration_seconds": (
                    round((session_end - session_start).total_seconds(), 3)
                    if session_start and session_end
                    else 0
                ),
                "excluded_intervals": exclusions,
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")
    verify_public_export(output, known_private_values=known_private)
    public_manifest = {
        "schema_version": "1.0",
        "policy_sha256": _sha256(Path(policy_path)),
        "feature_sha256": _sha256(output),
        "sessions": public_sessions,
    }
    output.with_suffix(".manifest.json").write_text(
        json.dumps(public_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "policy_version": policy.policy_version,
        "rows": len(rows),
        "sessions": len(session_labels),
        "tracks": len(track_labels),
        "splits": sorted({row["split"] for row in rows}),
        "public_manifest": output.with_suffix(".manifest.json").name,
    }
