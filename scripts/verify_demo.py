#!/usr/bin/env python3
"""Verify that the hardware-free demo works across every service boundary."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from dataclasses import asdict, dataclass
from urllib.request import urlopen

@dataclass(frozen=True)
class DemoEvidence:
    active_aircraft: int
    observations: int
    unique_observations: int
    observed_aircraft: int


def fetch_json(url: str) -> object:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - local URL is explicit input
        return json.load(response)


def fetch_text(url: str) -> str:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - local URL is explicit input
        return response.read().decode("utf-8")


def query_observation_evidence(database_container: str) -> tuple[int, int, int]:
    query = """
        SELECT
            count(*),
            count(DISTINCT observation_id),
            count(DISTINCT icao_hex)
        FROM track_observations
        WHERE source_type = 'SIMULATION'
          AND source_id = 'columbus-demo'
          AND received_at >= now() - interval '5 minutes'
    """
    result = subprocess.run(
        [
            "docker",
            "exec",
            database_container,
            "psql",
            "-U",
            "postgres",
            "-d",
            "adsb_intel",
            "-tAc",
            query,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    values = [int(value) for value in result.stdout.strip().split("|")]
    if len(values) != 3:
        raise RuntimeError(f"unexpected database evidence: {result.stdout!r}")
    return values[0], values[1], values[2]


def verify_once(
    *,
    api_url: str,
    frontend_url: str,
    database_container: str,
    minimum_aircraft: int,
    minimum_observations: int,
) -> DemoEvidence:
    health = fetch_json(f"{api_url}/health")
    if not isinstance(health, dict) or health.get("status") != "healthy":
        raise RuntimeError(f"backend health check failed: {health!r}")

    aircraft = fetch_json(f"{api_url}/api/v1/aircraft/?minutes=5")
    if not isinstance(aircraft, list) or len(aircraft) < minimum_aircraft:
        raise RuntimeError(f"expected at least {minimum_aircraft} active aircraft")

    frontend = fetch_text(frontend_url)
    if '<div id="root"></div>' not in frontend:
        raise RuntimeError("frontend did not return the React application shell")

    observations, unique_observations, observed_aircraft = query_observation_evidence(
        database_container
    )
    if observations < minimum_observations:
        raise RuntimeError(f"expected at least {minimum_observations} observations")
    if observations != unique_observations:
        raise RuntimeError("duplicate observation IDs were persisted")
    if observed_aircraft < minimum_aircraft:
        raise RuntimeError(f"expected observations for {minimum_aircraft} aircraft")

    return DemoEvidence(
        active_aircraft=len(aircraft),
        observations=observations,
        unique_observations=unique_observations,
        observed_aircraft=observed_aircraft,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--frontend-url", default="http://127.0.0.1:5173")
    parser.add_argument("--database-container", default="adsb-postgres")
    parser.add_argument("--minimum-aircraft", type=int, default=6)
    parser.add_argument("--minimum-observations", type=int, default=6)
    parser.add_argument("--timeout", type=float, default=180)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    deadline = time.monotonic() + args.timeout
    last_error: Exception | None = None

    while time.monotonic() < deadline:
        try:
            evidence = verify_once(
                api_url=args.api_url.rstrip("/"),
                frontend_url=args.frontend_url.rstrip("/"),
                database_container=args.database_container,
                minimum_aircraft=args.minimum_aircraft,
                minimum_observations=args.minimum_observations,
            )
            print(json.dumps({"status": "passed", **asdict(evidence)}, indent=2))
            return 0
        except Exception as error:  # Poll all startup dependency failures.
            last_error = error
            time.sleep(2)

    print(json.dumps({"status": "failed", "error": str(last_error)}, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
