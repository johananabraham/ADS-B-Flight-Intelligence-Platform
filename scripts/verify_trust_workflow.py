#!/usr/bin/env python3
"""Verify persisted trust evidence and the operator workflow end to end."""

from __future__ import annotations

import argparse
import json
import subprocess
from urllib.request import Request, urlopen

from verify_demo import fetch_json


ACTION_ID = "00000000-0000-4000-8000-000000000401"


def post_json(url: str, payload: dict[str, object] | None = None) -> object:
    body = json.dumps(payload or {}).encode("utf-8")
    request = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:  # noqa: S310 - explicit local URL
        return json.load(response)


def query_counts(container: str, assessment_id: str) -> tuple[int, int]:
    query = (
        "SELECT (SELECT count(*) FROM trust_assessments WHERE assessment_id = "
        f"'{assessment_id}'), (SELECT count(*) FROM trust_operator_actions "
        f"WHERE assessment_id = '{assessment_id}')"
    )
    result = subprocess.run(
        [
            "docker",
            "exec",
            container,
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
    assessment_count, action_count = result.stdout.strip().split("|")
    return int(assessment_count), int(action_count)


def verify(api_url: str, database_container: str) -> dict[str, object]:
    assessment_url = f"{api_url}/api/v1/trust/A0B0C0/assessments"
    first = post_json(assessment_url)
    retry = post_json(assessment_url)
    if not isinstance(first, dict) or not isinstance(retry, dict):
        raise RuntimeError("assessment endpoint did not return objects")
    if first.get("assessment", {}).get("state") != "QUESTIONABLE":
        raise RuntimeError(f"expected flagged evidence to be QUESTIONABLE: {first}")
    if first.get("assessment_id") != retry.get("assessment_id"):
        raise RuntimeError("identical evidence did not produce a stable assessment ID")
    if first.get("inserted") is not True or retry.get("inserted") is not False:
        raise RuntimeError("assessment retry was not idempotent")

    assessment_id = str(first["assessment_id"])
    action = {
        "action_id": ACTION_ID,
        "action_type": "ANNOTATE",
        "actor": "ci-verifier",
        "note": "Reviewed deterministic kinematic attack evidence.",
    }
    action_url = f"{api_url}/api/v1/trust-events/{assessment_id}/actions"
    first_action = post_json(action_url, action)
    retry_action = post_json(action_url, action)
    if first_action.get("inserted") is not True or retry_action.get("inserted") is not False:
        raise RuntimeError("operator action retry was not idempotent")

    events = fetch_json(
        f"{api_url}/api/v1/trust-events/?icao_hex=A0B0C0&state=QUESTIONABLE"
    )
    detail = fetch_json(f"{api_url}/api/v1/trust-events/{assessment_id}")
    exported = fetch_json(f"{api_url}/api/v1/trust-events/{assessment_id}/export")
    if not isinstance(events, list) or assessment_id not in {
        event.get("assessment_id") for event in events
    }:
        raise RuntimeError("filtered event history omitted the persisted assessment")
    if detail.get("actions", [{}])[0].get("identity_assurance") != "SELF_ASSERTED":
        raise RuntimeError("operator identity evidence boundary is missing")
    if not str(exported.get("identity_warning", "")).startswith("Operator labels"):
        raise RuntimeError("export omitted the identity warning")

    assessment_count, action_count = query_counts(database_container, assessment_id)
    if (assessment_count, action_count) != (1, 1):
        raise RuntimeError(
            f"expected one assessment and one action, got {assessment_count}/{action_count}"
        )
    return {
        "status": "passed",
        "assessment_id": assessment_id,
        "state": "QUESTIONABLE",
        "assessment_rows": assessment_count,
        "operator_action_rows": action_count,
        "identity_assurance": "SELF_ASSERTED",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--database-container", default="adsb-postgres")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = verify(args.api_url.rstrip("/"), args.database_container)
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error)}, indent=2))
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
