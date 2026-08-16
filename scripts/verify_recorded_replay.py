#!/usr/bin/env python3
"""Verify the checked-in recording through replay, ingestion, API, and PostgreSQL."""

from __future__ import annotations

import argparse
from http.cookiejar import CookieJar
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from urllib.request import HTTPCookieProcessor, OpenerDirector, Request, build_opener

from verify_demo import fetch_json, fetch_text


@dataclass(frozen=True)
class RecordedReplayEvidence:
    recording_id: str
    active_aircraft: int
    observations: int
    unique_observations: int
    observed_aircraft: int
    first_observed_at: str
    last_observed_at: str
    controls_verified: bool
    kinematic_evaluations: int
    kinematic_flags: int


def authenticate(
    api_url: str,
    *,
    username: str,
    password: str,
    origin: str,
) -> OpenerDirector:
    if not username or not password:
        raise RuntimeError("operator credentials are required to verify replay controls")
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    request = Request(
        f"{api_url}/api/v1/auth/login",
        data=json.dumps({"username": username, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Origin": origin},
        method="POST",
    )
    with opener.open(request, timeout=5) as response:  # noqa: S310 - local API
        result = json.load(response)
    if not isinstance(result, dict) or not isinstance(result.get("user"), dict):
        raise RuntimeError("operator login returned an invalid session response")
    return opener


def send_command(
    opener: OpenerDirector,
    api_url: str,
    action: str,
    *,
    origin: str,
    value: float | None = None,
) -> dict:
    request = Request(
        f"{api_url}/api/v1/replay/commands",
        data=json.dumps({"action": action, "value": value}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Origin": origin},
        method="POST",
    )
    with opener.open(request, timeout=5) as response:  # noqa: S310 - local API
        result = json.load(response)
    if not isinstance(result, dict):
        raise RuntimeError("replay command returned invalid status")
    return result


def verify_controls(
    api_url: str,
    *,
    username: str,
    password: str,
    origin: str,
) -> None:
    opener = authenticate(
        api_url,
        username=username,
        password=password,
        origin=origin,
    )
    restarted = send_command(opener, api_url, "restart", origin=origin)
    if restarted.get("state") != "PLAYING" or restarted.get("position_ms", 1) > 50:
        raise RuntimeError("restart did not reset and start playback")

    speed = send_command(opener, api_url, "speed", origin=origin, value=2)
    if speed.get("speed") != 2:
        raise RuntimeError("speed command was not applied")

    paused = send_command(opener, api_url, "pause", origin=origin)
    time.sleep(0.1)
    paused_status = fetch_json(f"{api_url}/api/v1/replay/status")
    if paused_status.get("state") != "PAUSED":
        raise RuntimeError("pause command was not applied")
    if paused_status.get("position_ms") != paused.get("position_ms"):
        raise RuntimeError("playback position changed while paused")

    sought = send_command(opener, api_url, "seek", origin=origin, value=1)
    if sought.get("position_ms") != 1_000 or sought.get("state") != "PAUSED":
        raise RuntimeError("seek did not preserve paused state at the requested position")

    resumed = send_command(opener, api_url, "resume", origin=origin)
    if resumed.get("state") != "PLAYING":
        raise RuntimeError("resume command was not applied")

    send_command(opener, api_url, "speed", origin=origin, value=1)
    send_command(opener, api_url, "restart", origin=origin)


def query_recording(
    database_container: str, recording_id: str, source_id: str
) -> tuple[str, ...]:
    query = """
        SELECT
            count(*),
            count(DISTINCT observation_id),
            count(DISTINCT icao_hex),
            to_char(min(observed_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
            to_char(max(observed_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
            (SELECT count(*) FROM kinematic_evaluations WHERE source_id = :'source_id'),
            (SELECT count(*) FROM kinematic_evaluations
                WHERE source_id = :'source_id' AND status = 'FLAGGED'),
            (SELECT count(*) FROM anomalies
                WHERE anomaly_type = 'KINEMATIC_PLAUSIBILITY'
                AND details->>'source_id' = :'source_id')
        FROM track_observations
        WHERE recording_id = :'recording_id'
    """
    result = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            database_container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "adsb_intel",
            "-v",
            f"recording_id={recording_id}",
            "-v",
            f"source_id={source_id}",
            "-tA",
        ],
        check=True,
        capture_output=True,
        input=query,
        text=True,
        timeout=10,
    )
    values = tuple(result.stdout.strip().split("|"))
    if len(values) != 8:
        raise RuntimeError(f"unexpected database evidence: {result.stdout!r}")
    return values


def verify_once(args: argparse.Namespace) -> RecordedReplayEvidence:
    health = fetch_json(f"{args.api_url}/health")
    if not isinstance(health, dict) or health.get("status") != "healthy":
        raise RuntimeError(f"backend health check failed: {health!r}")

    aircraft = fetch_json(f"{args.api_url}/api/v1/aircraft/?minutes=5")
    if not isinstance(aircraft, list) or len(aircraft) < args.expected_aircraft:
        raise RuntimeError(f"expected at least {args.expected_aircraft} active aircraft")
    if '<div id="root"></div>' not in fetch_text(args.frontend_url):
        raise RuntimeError("frontend did not return the React application shell")

    values = query_recording(args.database_container, args.recording_id, args.source_id)
    observations, unique_observations, observed_aircraft = map(int, values[:3])
    if observations != args.expected_observations:
        raise RuntimeError(f"expected exactly {args.expected_observations} immutable events")
    if unique_observations != observations:
        raise RuntimeError("duplicate observation IDs were persisted")
    if observed_aircraft != args.expected_aircraft:
        raise RuntimeError(f"expected exactly {args.expected_aircraft} recorded aircraft")
    if values[3] != args.expected_start or values[4] != args.expected_end:
        raise RuntimeError(f"recorded timestamps were not preserved: {values[3:]!r}")
    evaluations, flags, alerts = map(int, values[5:])
    if evaluations != args.expected_evaluations:
        raise RuntimeError(f"expected {args.expected_evaluations} kinematic evaluations")
    if flags or alerts:
        raise RuntimeError("clean fixture produced a kinematic flag or operator alert")

    verify_controls(
        args.api_url,
        username=args.operator_username,
        password=args.operator_password,
        origin=args.operator_origin,
    )

    return RecordedReplayEvidence(
        recording_id=args.recording_id,
        active_aircraft=len(aircraft),
        observations=observations,
        unique_observations=unique_observations,
        observed_aircraft=observed_aircraft,
        first_observed_at=values[3],
        last_observed_at=values[4],
        controls_verified=True,
        kinematic_evaluations=evaluations,
        kinematic_flags=flags,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    parser.add_argument("--database-container", default="adsb-postgres")
    parser.add_argument("--recording-id", default="columbus-generated-v2")
    parser.add_argument("--source-id", default="checked-in-recording-v2")
    parser.add_argument("--expected-observations", type=int, default=6)
    parser.add_argument("--expected-aircraft", type=int, default=2)
    parser.add_argument("--expected-evaluations", type=int, default=4)
    parser.add_argument("--expected-start", default="2026-07-19 12:00:00")
    parser.add_argument("--expected-end", default="2026-07-19 12:00:02")
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument(
        "--operator-username",
        default=os.getenv("DEMO_OPERATOR_USERNAME", ""),
    )
    parser.add_argument(
        "--operator-password",
        default=os.getenv("DEMO_OPERATOR_PASSWORD", ""),
    )
    parser.add_argument("--operator-origin", default="http://localhost:5173")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.api_url = args.api_url.rstrip("/")
    args.frontend_url = args.frontend_url.rstrip("/")
    deadline = time.monotonic() + args.timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            evidence = verify_once(args)
            print(json.dumps({"status": "passed", **asdict(evidence)}, indent=2))
            return 0
        except Exception as error:  # Poll all startup dependency failures.
            last_error = error
            time.sleep(2)

    print(json.dumps({"status": "failed", "error": str(last_error)}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
