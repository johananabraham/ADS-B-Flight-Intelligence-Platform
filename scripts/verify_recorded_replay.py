#!/usr/bin/env python3
"""Verify the checked-in recording through replay, ingestion, API, and PostgreSQL."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass

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


def query_recording(database_container: str, recording_id: str) -> tuple[str, ...]:
    query = """
        SELECT
            count(*),
            count(DISTINCT observation_id),
            count(DISTINCT icao_hex),
            to_char(min(observed_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS'),
            to_char(max(observed_at) AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')
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
            "-tA",
        ],
        check=True,
        capture_output=True,
        input=query,
        text=True,
        timeout=10,
    )
    values = tuple(result.stdout.strip().split("|"))
    if len(values) != 5:
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

    values = query_recording(args.database_container, args.recording_id)
    observations, unique_observations, observed_aircraft = map(int, values[:3])
    if observations != args.expected_observations:
        raise RuntimeError(f"expected exactly {args.expected_observations} immutable events")
    if unique_observations != observations:
        raise RuntimeError("duplicate observation IDs were persisted")
    if observed_aircraft != args.expected_aircraft:
        raise RuntimeError(f"expected exactly {args.expected_aircraft} recorded aircraft")
    if values[3] != args.expected_start or values[4] != args.expected_end:
        raise RuntimeError(f"recorded timestamps were not preserved: {values[3:]!r}")

    return RecordedReplayEvidence(
        recording_id=args.recording_id,
        active_aircraft=len(aircraft),
        observations=observations,
        unique_observations=unique_observations,
        observed_aircraft=observed_aircraft,
        first_observed_at=values[3],
        last_observed_at=values[4],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    parser.add_argument("--database-container", default="adsb-postgres")
    parser.add_argument("--recording-id", default="columbus-generated-v1")
    parser.add_argument("--expected-observations", type=int, default=6)
    parser.add_argument("--expected-aircraft", type=int, default=2)
    parser.add_argument("--expected-start", default="2026-07-19 12:00:00")
    parser.add_argument("--expected-end", default="2026-07-19 12:00:02")
    parser.add_argument("--timeout", type=float, default=60)
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
