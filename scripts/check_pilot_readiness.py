#!/usr/bin/env python3
"""Verify that a local feeder sidecar is producing pilot-quality evidence."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen


LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}


def assess(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    health: Mapping[str, Any],
) -> dict[str, Any]:
    checks = {
        "schema_supported": before.get("schema_version") == after.get("schema_version") == "1.0",
        "same_process_session": bool(before.get("pilot_session_id"))
        and before.get("pilot_session_id") == after.get("pilot_session_id"),
        "source_connected": health.get("connection") == "CONNECTED",
        "messages_advancing": int(after.get("parsed_messages_total", 0))
        > int(before.get("parsed_messages_total", 0)),
        "evaluations_advancing": int(after.get("observations_evaluated_total", 0))
        > int(before.get("observations_evaluated_total", 0)),
        "no_dropped_messages": int(after.get("dropped_messages_total", -1)) == 0,
        "queue_within_capacity": int(health.get("queue_depth", 0))
        < int(health.get("queue_capacity", 0)),
        "privacy_boundary_present": "no aircraft identifiers"
        in str(after.get("privacy_boundary", "")).lower(),
    }
    return {
        "schema_version": "1.0",
        "status": "READY" if all(checks.values()) else "NOT_READY",
        "checks": checks,
        "pilot_summary": dict(after),
    }


def _read_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - loopback URL validated
        if response.status != 200:
            raise RuntimeError(f"sidecar returned HTTP {response.status}")
        value = json.load(response)
    if not isinstance(value, dict):
        raise RuntimeError("sidecar returned a non-object response")
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8090")
    parser.add_argument("--sample-seconds", type=int, default=5)
    args = parser.parse_args()
    parsed = urlparse(args.base_url)
    if parsed.scheme != "http" or parsed.hostname not in LOOPBACK_HOSTS:
        parser.error("base URL must be an HTTP loopback address")
    if not 1 <= args.sample_seconds <= 60:
        parser.error("sample-seconds must be between 1 and 60")
    base = args.base_url.rstrip("/")
    try:
        before = _read_json(f"{base}/api/v1/pilot/summary")
        time.sleep(args.sample_seconds)
        after = _read_json(f"{base}/api/v1/pilot/summary")
        health = _read_json(f"{base}/api/v1/integrity/health")
    except (HTTPError, URLError, TimeoutError, RuntimeError) as exc:
        parser.exit(1, f"pilot readiness failed: {exc}\n")
    result = assess(before, after, health)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "READY":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
